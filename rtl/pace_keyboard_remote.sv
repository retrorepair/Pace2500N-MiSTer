// SPDX-License-Identifier: GPL-3.0-only
// MiSTer hps_io key event -> Pace handset raw byte; no host OS code assumptions.
// Source mapping: re/KEYBOARD_REMOTE_MAP.csv. F12 remains MiSTer OSD.
module pace_keyboard_remote (
 input wire clk, reset,
 input wire [10:0] ps2_key,
 output reg event_valid=0, event_pressed=0,
 output reg [7:0] remote_code=0,
 output reg [31:0] event_count=0
);
 reg last_toggle=0;
 reg mapped;
 reg [7:0] decoded;
 always @* begin
  mapped=1; decoded=0;
  case(ps2_key[8:0])
   9'h005:decoded=8'hCC; // F1: TV Guide
   9'h006:decoded=8'h7D; // F2: Box Office
   9'h004:decoded=8'h7E; // F3: Services
   9'h00C:decoded=8'hF5; // F4: Interactive
   9'h003:decoded=8'h80; // F5: Sky / return to TV
   9'h00B:decoded=8'hCB; // F6: Information
   9'h083:decoded=8'h81; // F7: Help
   9'h00A:decoded=8'h3C; // F8: Text
   9'h001:decoded=8'h0C; // F9: Standby
   9'h009:decoded=8'h84; // F10: TV
   9'h175:decoded=8'h58; // Up: Up
   9'h172:decoded=8'h59; // Down: Down
   9'h16B:decoded=8'h5A; // Left: Left
   9'h174:decoded=8'h5B; // Right: Right
   9'h05A:decoded=8'h5C; // Enter: Select
   9'h15A:decoded=8'h5C; // Keypad Enter: Select
   9'h076:decoded=8'h83; // Escape: Back Up
   9'h066:decoded=8'h83; // Backspace: Back Up
   9'h17D:decoded=8'h20; // Page Up: Channel +
   9'h17A:decoded=8'h21; // Page Down: Channel -
   9'h02D:decoded=8'h6D; // R: Red
   9'h034:decoded=8'h6E; // G: Green
   9'h035:decoded=8'h6F; // Y: Yellow
   9'h032:decoded=8'h70; // B: Blue
   9'h043:decoded=8'hCB; // I: Information
   9'h033:decoded=8'h81; // H: Help
   9'h02C:decoded=8'h3C; // T: Text
   9'h01B:decoded=8'h80; // S: Sky / return to TV
   9'h04D:decoded=8'h0C; // P: Standby
   9'h029:decoded=8'h3E; // Space: Play
   9'h03B:decoded=8'h24; // J: Pause
   9'h042:decoded=8'h3F; // K: Stop
   9'h021:decoded=8'h40; // C: Record
   9'h054:decoded=8'h3D; // [: Rewind
   9'h05B:decoded=8'h28; // ]: Fast Forward
   9'h045:decoded=8'h00; // 0: 0
   9'h016:decoded=8'h01; // 1: 1
   9'h01E:decoded=8'h02; // 2: 2
   9'h026:decoded=8'h03; // 3: 3
   9'h025:decoded=8'h04; // 4: 4
   9'h02E:decoded=8'h05; // 5: 5
   9'h036:decoded=8'h06; // 6: 6
   9'h03D:decoded=8'h07; // 7: 7
   9'h03E:decoded=8'h08; // 8: 8
   9'h046:decoded=8'h09; // 9: 9
   default:mapped=0;
  endcase
 end
 always @(posedge clk) begin
  event_valid<=0;
  if(reset)begin last_toggle<=ps2_key[10];event_count<=0;event_pressed<=0;remote_code<=0;end
  else if(last_toggle!=ps2_key[10])begin
   last_toggle<=ps2_key[10];
   if(mapped)begin event_valid<=1;event_pressed<=ps2_key[9];remote_code<=decoded;event_count<=event_count+1'b1;end
  end
 end
endmodule
