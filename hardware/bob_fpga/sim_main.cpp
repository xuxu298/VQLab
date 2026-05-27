// Verilator self-checking testbench for bob_gating.v (H2 Bob FPGA firmware).
//
// Drives the firmware gate-by-gate through named scenarios that pin down the three behaviours
// the analog self-differencing front-end cannot do itself: SD ghost-reject, afterpulse gate-veto,
// and event timestamping. Prints PASS/FAIL per check and exits non-zero on any failure, so it
// doubles as the firmware's regression test (run from tests/test_firmware.py).
//
// Build+run (Verilator >= 4.0):  see sim.py  /  verilator --cc --exe --build ...

#include "Vbob_gating.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>

static Vbob_gating* dut = nullptr;
static int n_checks = 0, n_fail = 0;

struct Sample {
    bool     event_valid;
    uint64_t event_ts;
    uint32_t n_accepted, n_ghost, n_afterpulse;
    bool     veto_active;
};

// One gate period: present (arm, click) while clk low, then a rising edge; sample after.
static Sample step(bool arm, bool click) {
    dut->arm = arm; dut->click = click;
    dut->clk = 0; dut->eval();
    dut->clk = 1; dut->eval();
    return Sample{ (bool)dut->event_valid, (uint64_t)dut->event_ts,
                   (uint32_t)dut->n_accepted, (uint32_t)dut->n_ghost,
                   (uint32_t)dut->n_afterpulse, (bool)dut->veto_active };
}

static void reset() {
    dut->rst = 1; dut->arm = 0; dut->click = 0;
    dut->clk = 0; dut->eval(); dut->clk = 1; dut->eval();
    dut->clk = 0; dut->eval(); dut->clk = 1; dut->eval();
    dut->rst = 0;
}

static void check(const char* what, bool ok) {
    n_checks++;
    if (!ok) { n_fail++; printf("  [FAIL] %s\n", what); }
    else     { printf("  [ ok ] %s\n", what); }
}

// Read a "+key=value" plusarg (for the qsim co-simulation stream mode).
static double plus_val(const char* key, double def) {
    std::string m = Verilated::commandArgsPlusMatch(key);
    if (m.empty()) return def;
    auto pos = m.find('=');
    return pos == std::string::npos ? def : atof(m.c_str() + pos + 1);
}

// Stream mode: drive a pseudo-random Bernoulli(pclick) comparator stream and report telemetry.
// Lets hardware/bob_fpga/validate_with_qsim.py feed the firmware the qsim detector's click
// statistics and read back the firmware-enforced dead-time throttling. Prints one parseable line.
static int run_stream() {
    long veto   = (long)plus_val("veto=", 4);
    double p    = plus_val("pclick=", 0.05);
    long gates  = (long)plus_val("gates=", 1000000);
    long seed   = (long)plus_val("seed=", 1);
    reset(); dut->veto_cycles = veto;
    std::mt19937_64 rng((uint64_t)seed);
    std::uniform_real_distribution<double> u(0.0, 1.0);
    long n_in = 0;
    Sample s{};
    for (long g = 0; g < gates; g++) {
        bool c = u(rng) < p;
        if (c) n_in++;
        s = step(true, c);
    }
    printf("STREAM veto=%ld pclick=%g gates=%ld n_in=%ld n_accepted=%u n_ghost=%u n_afterpulse=%u\n",
           veto, p, gates, n_in, s.n_accepted, s.n_ghost, s.n_afterpulse);
    return 0;
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    dut = new Vbob_gating;

    if (!std::string(Verilated::commandArgsPlusMatch("stream")).empty()) {
        int rc = run_stream();
        delete dut;
        return rc;
    }

    // -- A: a single photon produces exactly one timestamped event at the right gate index ----
    printf("A: single photon -> one timestamped event\n");
    reset(); dut->veto_cycles = 4;
    step(true, false); step(true, false); step(true, false);   // gates 0,1,2 idle
    Sample s = step(true, true);                                // gate 3: a photon
    check("event strobed on the photon gate", s.event_valid);
    check("timestamp == gate index 3", s.event_ts == 3);
    check("accepted count == 1", s.n_accepted == 1);

    // -- B: the self-differencing inverted ghost (next gate) is rejected ----------------------
    printf("B: SD ghost (gate k+1) rejected\n");
    reset(); dut->veto_cycles = 4;
    s = step(true, true);                                       // gate 0: accept
    check("photon accepted at gate 0", s.event_valid && s.event_ts == 0);
    s = step(true, true);                                       // gate 1: the ghost
    check("no event on the ghost gate", !s.event_valid);
    check("classified as ghost (n_ghost==1)", s.n_ghost == 1);
    check("still only 1 accepted", s.n_accepted == 1);

    // -- C: afterpulse hold-off vetoes veto_cycles gates, then re-arms exactly ----------------
    printf("C: afterpulse gate-veto + re-arm timing (veto_cycles=4)\n");
    reset(); dut->veto_cycles = 4;
    step(true, true);                                           // gate 0: accept
    step(true, true);                                           // gate 1: ghost (rejected)
    s = step(true, true);                                       // gate 2: afterpulse
    check("gate 2 vetoed (afterpulse)", !s.event_valid && s.n_afterpulse == 1);
    s = step(true, true);                                       // gate 3
    s = step(true, true);                                       // gate 4
    check("gates 3,4 vetoed (afterpulse==3)", !s.event_valid && s.n_afterpulse == 3);
    s = step(true, true);                                       // gate 5: re-armed
    check("re-armed at gate 5 (veto window = 4 gates)", s.event_valid);
    check("re-armed event timestamp == 5", s.event_ts == 5);
    check("accepted count == 2", s.n_accepted == 2);

    // -- D: the ghost is rejected even with veto_cycles=0 (it is an SD artifact, not afterpulse)
    printf("D: ghost-reject is independent of the afterpulse setting (veto_cycles=0)\n");
    reset(); dut->veto_cycles = 0;
    s = step(true, true);  check("gate 0 accepted", s.event_valid && s.n_accepted == 1);
    s = step(true, true);  check("gate 1 ghost rejected", !s.event_valid && s.n_ghost == 1);
    s = step(true, true);  check("gate 2 re-armed immediately (no afterpulse window)",
                                 s.event_valid && s.event_ts == 2 && s.n_accepted == 2);

    // -- E: disarm ignores clicks AND freezes the timestamp counter ---------------------------
    printf("E: disarm ignores clicks and freezes the gate counter\n");
    reset(); dut->veto_cycles = 0;
    s = step(true, true);  check("gate 0 accepted (ts 0)", s.event_valid && s.event_ts == 0);
    for (int i = 0; i < 5; i++) {                               // 5 disarmed gates, clicking
        s = step(false, true);
        check("no event while disarmed", !s.event_valid);
    }
    s = step(true, true);                                       // re-arm: next active gate
    check("accepts on re-arm", s.event_valid);
    check("timestamp froze during disarm (ts==1, not 6)", s.event_ts == 1);

    // -- F: under continuous clicks the max count rate is gate_rate/(veto_cycles+1) ------------
    printf("F: saturated throughput == 1/(veto_cycles+1) (dead-time-limited)\n");
    reset(); dut->veto_cycles = 4;
    for (int g = 0; g < 50; g++) step(true, true);             // click every gate, 50 gates
    s = step(false, false);                                     // settle / read telemetry
    check("10 accepts in 50 saturated gates (period 5)", s.n_accepted == 10);

    // -- G: timestamps are strictly monotonic across a sparse stream --------------------------
    printf("G: timestamps strictly increasing across well-separated photons\n");
    reset(); dut->veto_cycles = 3;
    uint64_t last = 0; bool first = true, mono = true; int got = 0;
    for (int g = 0; g < 40; g++) {
        bool click = (g % 8 == 0);                              // a photon every 8 gates (>veto)
        s = step(true, click);
        if (s.event_valid) {
            got++;
            if (!first && !(s.event_ts > last)) mono = false;
            last = s.event_ts; first = false;
        }
    }
    check("all well-separated photons accepted (5)", got == 5);
    check("timestamps strictly increasing", mono);

    printf("\n%d checks, %d failed\n", n_checks, n_fail);
    delete dut;
    return n_fail == 0 ? 0 : 1;
}
