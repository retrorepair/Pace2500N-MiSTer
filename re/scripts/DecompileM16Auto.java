// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.symbol.*;
import java.math.BigInteger;
import java.io.PrintWriter;
import java.util.*;
// Read-only helper: for each MIPS16 code address, locate the enclosing function by scanning back to
// the nearest "addiu sp,-N" (0x63 80..FF) prologue, disassemble, create a function and decompile it.
public class DecompileM16Auto extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();DecompInterface d=new DecompInterface();
  d.openProgram(currentProgram);
  Register isa=currentProgram.getRegister("ISA_MODE");
  Set<Long> done=new HashSet<>();
  try(PrintWriter out=new PrintWriter(args[0])) {
   for(int i=1;i<args.length;i++) {
    long target=Long.parseUnsignedLong(args[i],16)&~1L;
    long start=-1;
    for(long a=target;a>target-0x1000;a-=2){
      int h=getShort(toAddr(a))&0xffff;
      if((h&0xff80)==0x6380){
        // accept only if preceded by a return delay slot, padding, or pool (heuristic: previous halfword is not an EXTEND prefix)
        int prev=getShort(toAddr(a-2))&0xffff;
        if((prev&0xf800)==0xf000)continue;
        start=a;break;
      }
    }
    if(start<0){out.println("\n// "+args[i]+": no prologue found");continue;}
    if(!done.add(start)){out.println("\n// "+args[i]+" in already printed function "+Long.toHexString(start));continue;}
    Address s=toAddr(start);
    Function f=getFunctionAt(s);
    if(f==null){
      Address e=s.add(0x800);
      clearListing(s,e);
      currentProgram.getProgramContext().setValue(isa,s,e,BigInteger.ONE);
      disassemble(s);
      f=createFunction(s,null);
    }
    if(f==null){out.println("\n// "+args[i]+": could not create function at "+s);continue;}
    DecompileResults r=d.decompileFunction(f,90,monitor);
    out.println("\n// ===== "+args[i]+" is inside function "+s+" body "+f.getBody());
    out.println(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());
   }
  } finally {d.dispose();}
 }
}
