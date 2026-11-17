`timescale 1ns/1ps

module tb_mp2_recovery;
    localparam FRAME_BYTES = 576; // 192 kbps at 48 kHz
    localparam FRAMES = 32;
    localparam DAMAGED_FRAME = 8;

    reg clk = 0;
    always #10 clk = ~clk;

    reg reset = 1, write_byte = 0;
    reg [7:0] data;
    wire full, error, audio_valid;
    reg [25:0] sample_phase = 0;
    wire audio_ce = sample_phase >= 26'd49952000;

    always @(posedge clk)
        sample_phase <= sample_phase + 26'd48000 - (audio_ce ? 26'd50000000 : 26'd0);

    mp2_decode #(.PCM_AW(10)) decoder (
        .clk(clk), .rst(reset), .wr_en(write_byte), .wr_data(data), .full(full),
        .aud_ce(audio_ce), .audio_l(), .audio_r(), .aud_valid(audio_valid),
        .synced(), .err_unsupported(error), .fs_o(), .dbg_s_nz(), .dbg_pcm_nz(),
        .cp_step(1'b0), .cp_q()
    );

    integer offset, frame_byte, samples = 0, tail_samples = 0;

    always @(posedge clk) begin
        if (audio_valid) begin
            samples <= samples + 1;
            if (offset >= (FRAMES - 4) * FRAME_BYTES)
                tail_samples <= tail_samples + 1;
        end
    end

    initial begin
        repeat (10) @(negedge clk);
        reset = 0;
        for (offset = 0; offset < FRAMES * FRAME_BYTES; offset++) begin
            if (full) $fatal(1, "Fixture exceeded the input FIFO capacity");
            frame_byte = offset % FRAME_BYTES;
            case (frame_byte)
                0: data = 8'hff;
                1: data = 8'hfd;
                2: data = 8'ha4;
                3: data = 8'h04;
                default: data = 8'h00; // Zero allocation encodes silence
            endcase

            // Maximal allocations overrun the frame. The first channel in
            // the first subband uses one scalefactor where the others use
            // three, so the overrun ends between bytes.
            if (offset / FRAME_BYTES == DAMAGED_FRAME) begin
                if (frame_byte >= 4 && frame_byte < 26) data = 8'hff;
                if (frame_byte == 26) data = 8'h80;
            end
            write_byte = 1;
            @(negedge clk);
            write_byte = 0;
            repeat (2082) @(negedge clk); // 24,000 input bytes/s at 50 MHz
        end

        if (!error) $fatal(1, "The fixture did not trigger the MP2 error path");
        if (tail_samples < 4000) $fatal(1, "Audio did not recover, tail samples = %d", tail_samples);
        $display("MP2 audio recovered, %0d PCM pairs total and %0d in the final four frames", samples, tail_samples);
        $finish;
    end
endmodule
