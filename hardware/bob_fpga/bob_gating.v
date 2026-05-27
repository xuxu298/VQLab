// Bob detector FPGA firmware — gate-veto + self-differencing ghost-reject + event timestamping.
//
// Subsystem H2 (firmware for the H1 self-differencing gating board, docs/03 §7 step 4). One
// detector channel. Every gate period the self-differencing front-end (SPAD -> 180° hybrid ->
// LNA -> ADCMP fast comparator, docs/03 §3/§5) produces at most one LVDS event; after SERDES
// deserialization into the gate-clock domain that becomes the 1-bit `click` sample below.
//
// The firmware does three jobs the analog front-end cannot:
//   1. GHOST-REJECT   — self-differencing leaves an inverted copy of every real avalanche exactly
//                        one gate period later (docs/03 §3). The gate immediately after an
//                        accepted click is always vetoed, independent of the afterpulse setting.
//   2. GATE-VETO       — afterpulsing: trapped charges re-trigger the SPAD for a few ns after a
//                        click. `veto_cycles` gates are held off after each accepted click
//                        (= the detector dead time; docs/03 §5). The ghost gate is its first gate.
//   3. TIMESTAMP       — each accepted photon is tagged with the running gate index and strobed
//                        out (event_valid + event_ts) — the time-tag Bob sifts/aligns on. In the
//                        physical board this word is serialized back over LVDS to the TDC/host.
//
// Synthesizable, single clock (the gate clock, e.g. 1.25 GHz), synchronous active-high reset.
module bob_gating #(
    parameter integer TS_WIDTH   = 48,   // gate-index timestamp width
    parameter integer CNT_WIDTH  = 32,   // telemetry counter width
    parameter integer VETO_WIDTH = 16    // veto-length field width
) (
    input  wire                   clk,          // gate clock
    input  wire                   rst,          // synchronous, active-high
    input  wire                   arm,          // 1 = detector armed (gates active / counting)
    input  wire                   click,        // comparator fired this gate (post-SD, positive disc.)
    input  wire [VETO_WIDTH-1:0]  veto_cycles,  // afterpulse hold-off in gates (>=1; ghost is gate 1)

    output reg                    event_valid,  // 1-cycle strobe: an accepted photon was timestamped
    output reg  [TS_WIDTH-1:0]    event_ts,     // gate index of the accepted click
    output wire                   veto_active,   // status: currently in hold-off
    output reg  [CNT_WIDTH-1:0]   n_accepted,   // telemetry: accepted photons
    output reg  [CNT_WIDTH-1:0]   n_ghost,      // telemetry: clicks rejected as the SD ghost
    output reg  [CNT_WIDTH-1:0]   n_afterpulse  // telemetry: clicks rejected during afterpulse hold-off
);
    reg [TS_WIDTH-1:0]   gate_ctr;    // free-running gate index = the timestamp source
    reg [VETO_WIDTH-1:0] veto_rem;    // gates remaining in the afterpulse hold-off
    reg                  ghost_gate;  // high exactly one gate after an accepted click (the SD ghost)

    assign veto_active = (veto_rem != {VETO_WIDTH{1'b0}}) | ghost_gate;

    // Accept a photon only when armed, with no pending ghost and no afterpulse hold-off.
    wire accept = arm & click & (veto_rem == {VETO_WIDTH{1'b0}}) & ~ghost_gate;

    always @(posedge clk) begin
        if (rst) begin
            gate_ctr     <= {TS_WIDTH{1'b0}};
            veto_rem     <= {VETO_WIDTH{1'b0}};
            ghost_gate   <= 1'b0;
            event_valid  <= 1'b0;
            event_ts     <= {TS_WIDTH{1'b0}};
            n_accepted   <= {CNT_WIDTH{1'b0}};
            n_ghost      <= {CNT_WIDTH{1'b0}};
            n_afterpulse <= {CNT_WIDTH{1'b0}};
        end else begin
            event_valid <= 1'b0;        // default; pulsed high only on accept
            ghost_gate  <= 1'b0;        // default; set only by an accept (marks the next gate)
            if (arm) begin
                gate_ctr <= gate_ctr + 1'b1;          // advance the gate index every armed gate
                if (accept) begin
                    event_valid <= 1'b1;
                    event_ts    <= gate_ctr;
                    n_accepted  <= n_accepted + 1'b1;
                    veto_rem    <= veto_cycles;        // open the hold-off window
                    ghost_gate  <= 1'b1;               // next gate is the SD ghost -> veto it
                end else begin
                    if (veto_rem != {VETO_WIDTH{1'b0}})
                        veto_rem <= veto_rem - 1'b1;   // count down the hold-off
                    if (click) begin                   // a click we are rejecting — classify it
                        if (ghost_gate)
                            n_ghost <= n_ghost + 1'b1;
                        else if (veto_rem != {VETO_WIDTH{1'b0}})
                            n_afterpulse <= n_afterpulse + 1'b1;
                    end
                end
            end
        end
    end
endmodule
