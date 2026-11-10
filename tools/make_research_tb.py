from pathlib import Path
s=Path('sim/tb_strict.sv').read_text().replace('module tb_strict;','module tb_research;')
s=s.replace('pace_firmware_cpu DUT (','pace_firmware_cpu #(.EXPERIMENTAL_READY(1)) DUT (').replace(".full_flash_loaded(1'b0),.mmio_policy(2'd0)",".full_flash_loaded(1'b1),.mmio_policy(2'd1)")
s=s.replace('reg [63:0] ram[0:2097151];', '''reg [63:0] ram[0:2097151];
  reg [63:0] flash[0:262143];
  initial $readmemh("sim/fullflash_ddr.hex",flash);''')
s=s.replace("if(addr<29'h06000000 || addr>=29'h06200000)","if(!((addr>=29'h06000000 && addr<29'h06200000) || (addr>=29'h06400000 && addr<29'h06440000)))")
s=s.replace("rdata<=ram[addr-29'h06000000];", "rdata<=addr>=29'h06400000 ? flash[addr-29'h06400000] : ram[addr-29'h06000000];")
a=s.index('    wait(halt!=0 || retired>=3200000);')
b=s.index('    $finish;',a)
s=s[:a]+'''    wait(halt!=0 || retired>=8000000);
    if(halt!=0)$fatal(1,"Research halt=%h PC=%h IR=%h RET=%d",halt,pc,instruction,retired);
    if(DUT.interrupt_count<20 || DUT.extract_ddr(ram['h8428>>3],4,2,0)<10)
      $fatal(1,"Firmware timer not advancing IRQ=%d tickraw=%h",DUT.interrupt_count,ram['h8428>>3]);
    $display("PASS: experimental real U202 8M instructions PC=%h IRQ=%d tick=%h guessed=%d MMIO=%d",pc,DUT.interrupt_count,DUT.extract_ddr(ram['h8428>>3],4,2,0),guessed,mmio_count);
'''+s[b:]
Path('sim/tb_research.sv').write_text(s)
f=Path('firmware/FLASH_U202.bin').read_bytes()
Path('sim/fullflash_ddr.hex').write_text(''.join(f'{int.from_bytes(f[a:a+8],"little"):016x}\n' for a in range(0,len(f),8)))
