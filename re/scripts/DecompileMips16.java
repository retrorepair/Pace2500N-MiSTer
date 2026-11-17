// Decompile and list the function at each address, creating it as MIPS16 (ISA_MODE=1) where
// Ghidra has none. Args: OUT_FILE ADDR... Run with -readOnly: nothing is saved.
// @category Pace
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import java.io.PrintWriter;

public class DecompileMips16 extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(args[0]);
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        for (int i = 1; i < args.length; i++) {
            Address a = toAddr(Long.parseLong(args[i], 16));
            Function f = getFunctionContaining(a);
            if (f == null) {        // MIPS16 code: set ISA_MODE, disassemble, make a function
                ghidra.program.model.lang.Register isa = currentProgram.getRegister("ISA_MODE");
                clearListing(a, a.add(0x5ff));
                currentProgram.getProgramContext().setValue(isa, a, a.add(0x5ff), java.math.BigInteger.ONE);
                disassemble(a);
                f = createFunction(a, null);
            }
            out.println("// ===== " + args[i] + (f == null ? " (no function)" : " in " + f.getName() + " body " + f.getBody()));
            if (f == null) continue;
            DecompileResults r = d.decompileFunction(f, 120, monitor);
            out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed: " + r.getErrorMessage());
            out.println("// ----- listing");
            for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true)) {
                out.println(ins.getAddress() + "  " + ins);
            }
        }
        out.close();
    }
}
