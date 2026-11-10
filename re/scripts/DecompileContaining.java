// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import java.io.PrintWriter;
import java.util.*;
// Read-only: decompile the functions containing the given addresses and list their callers.
public class DecompileContaining extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();DecompInterface d=new DecompInterface();
  d.openProgram(currentProgram);
  Set<Address> done=new HashSet<>();
  try(PrintWriter out=new PrintWriter(args[0])) {
   for(int i=1;i<args.length;i++) {
    Address a=toAddr(Long.parseUnsignedLong(args[i],16));
    Function f=getFunctionContaining(a);
    if(f==null){
      Function before=getFunctionBefore(a);
      out.println("\n// "+a+" not inside a defined function; previous function "+(before==null?"none":before.getEntryPoint()+" "+before.getName()+" body "+before.getBody()));
      Instruction ins=getInstructionContaining(a);
      out.println("// instruction: "+ins);
      continue;
    }
    if(!done.add(f.getEntryPoint())){out.println("\n// "+a+" in already printed "+f.getEntryPoint());continue;}
    out.println("\n// "+a+" is inside "+f.getEntryPoint()+" "+f.getName()+" body "+f.getBody());
    StringBuilder callers=new StringBuilder();
    for(Reference r:getReferencesTo(f.getEntryPoint())){
      Function cf=getFunctionContaining(r.getFromAddress());
      callers.append(" "+r.getFromAddress()+"("+(cf==null?"?":cf.getEntryPoint().toString())+","+r.getReferenceType()+")");
    }
    out.println("// refs to entry:"+callers);
    DecompileResults r=d.decompileFunction(f,60,monitor);
    out.println(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());
   }
  } finally {d.dispose();}
 }
}
