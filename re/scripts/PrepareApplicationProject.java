// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.*;
import ghidra.program.model.address.*;
import java.io.*;

public class PrepareApplicationProject extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();Memory memory=currentProgram.getMemory();
  File input=new File(args[0]);
  for(long base:new long[]{0x9fc00000L,0xbfc00000L}) {
   Address address=toAddr(base);
   if(memory.getBlock(address)==null) {
    try(InputStream stream=new FileInputStream(input)) {
     MemoryBlock block=memory.createInitializedBlock(base==0x9fc00000L?"U202_cached":"U202_uncached",address,stream,input.length(),monitor,false);
     block.setRead(true);block.setWrite(false);block.setExecute(true);
    }
   }
  }
  Address end=toAddr(0x81000000L);
  Address start=toAddr(0x80106288L);
  if(memory.getBlock(start)==null) {
   MemoryBlock block=memory.createUninitializedBlock("RAM_uninitialized",start,end.subtract(start),false);
   block.setRead(true);block.setWrite(true);block.setExecute(true);
  }
  createLabel(toAddr(0x80000400L),"application_RAM_start",true);
  createLabel(toAddr(0xbfc2048cL),"application_cold_start",true);
  createLabel(toAddr(0x800296f0L),"peer_command53_three_bytes",true);
  createLabel(toAddr(0x80029724L),"peer_command54_one_byte",true);
  createLabel(toAddr(0x800cde9cL),"application_Nucleus_initialize",true);
  println("Mapped original U202 aliases and uninitialized RAM; no fabricated initialized BSS.");
 }
}
