// Generated from actual guest filter writes in the 200M checkpoint.
function automatic [31:0] match_seed_word(input [7:0] index);
 begin case(index)
  8'h10:match_seed_word=32'h40ff0000;
  8'h20:match_seed_word=32'h42ff0000;
  8'h50:match_seed_word=32'h000073ff;
  8'h69:match_seed_word=32'h00000400;
  8'h79:match_seed_word=32'h00000020;
  8'h89:match_seed_word=32'h00000008;
  8'ha9:match_seed_word=32'h04000000;
  8'hb9:match_seed_word=32'h08000000;
  8'hc9:match_seed_word=32'h10000000;
  8'hd0:match_seed_word=32'h80008000;
  8'hd1:match_seed_word=32'h10001000;
  8'hd2:match_seed_word=32'h6b006b00;
  8'hd3:match_seed_word=32'he419e419;
  8'hd4:match_seed_word=32'h00800080;
  8'hd5:match_seed_word=32'h00020002;
  8'hd6:match_seed_word=32'h00430043;
  8'hd7:match_seed_word=32'h002b002b;
  8'hd9:match_seed_word=32'h20000000;
  8'he0:match_seed_word=32'h80008000;
  8'he1:match_seed_word=32'h10001000;
  8'he2:match_seed_word=32'h6b006b00;
  8'he3:match_seed_word=32'he419e419;
  8'he4:match_seed_word=32'h00800080;
  8'he5:match_seed_word=32'h00020002;
  8'he6:match_seed_word=32'h00430043;
  8'he7:match_seed_word=32'h002b002b;
  8'he9:match_seed_word=32'h40000000;
  8'hf0:match_seed_word=32'h80008000;
  8'hf1:match_seed_word=32'h10001000;
  8'hf2:match_seed_word=32'h6b006b00;
  8'hf3:match_seed_word=32'he419e419;
  8'hf4:match_seed_word=32'h00800080;
  8'hf5:match_seed_word=32'h00020002;
  8'hf6:match_seed_word=32'h00430043;
  8'hf7:match_seed_word=32'h002b002b;
  8'hf9:match_seed_word=32'h80000000;
  default:match_seed_word=32'd0;
 endcase end
endfunction
