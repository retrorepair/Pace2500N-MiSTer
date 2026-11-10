// Independent one-instruction/delay-slot oracle using Ghidra's p-code emulator.
// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import com.google.gson.*;
import java.nio.file.*;
import java.math.BigInteger;
import java.util.Map;

public class Mips16Oracle extends GhidraScript {
    static final String[] REGS={"zero","at","v0","v1","a0","a1","a2","a3",
        "t0","t1","t2","t3","t4","t5","t6","t7","s0","s1","s2","s3",
        "s4","s5","s6","s7","t8","t9","k0","k1","gp","sp","s8","ra"};
    byte[] bytes(String value) { return java.util.HexFormat.of().parseHex(value); }
    Address address(String value) { return toAddr(Long.parseUnsignedLong(value.replace("0x",""),16)); }
    public void run() throws Exception {
        JsonArray input=JsonParser.parseString(Files.readString(Path.of(getScriptArgs()[0]))).getAsJsonArray();
        JsonArray output=new JsonArray();
        Address ram=toAddr(0x80000000L);
        if(currentProgram.getMemory().getBlock(ram)==null)
            currentProgram.getMemory().createInitializedBlock("oracle_ram",ram,0x10000,(byte)0,monitor,false);
        for(JsonElement element:input) {
            JsonObject test=element.getAsJsonObject();
            JsonObject result=new JsonObject();result.add("id",test.get("id"));
            EmulatorHelper emu=new EmulatorHelper(currentProgram);
            final int[] isaMode={test.has("isa_mode")?test.get("isa_mode").getAsInt():1};
            emu.registerCallOtherCallback("setISAMode",new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) {
                    long value=emu.getEmulator().getMemState().getValue(op.getInput(1));
                    isaMode[0]=(int)(value&1);
                    return true;
                }
            });
            try {
                for(String register:REGS) emu.writeRegister(register,0L);
                emu.writeRegister("hi",0L);emu.writeRegister("lo",0L);
                Address start=address(test.has("pc")?test.get("pc").getAsString():"bfc1f000");
                emu.writeMemory(start,bytes(test.get("code").getAsString()));
                emu.setContextRegister(currentProgram.getRegister("ISA_MODE"),BigInteger.valueOf(isaMode[0]));
                emu.writeRegister(emu.getPCRegister(),start.getOffset());
                if(test.has("regs")) for(Map.Entry<String,JsonElement> e:test.getAsJsonObject("regs").entrySet())
                    emu.writeRegister(e.getKey(),new BigInteger(e.getValue().getAsString().replace("0x",""),16));
                if(test.has("memory")) for(Map.Entry<String,JsonElement> e:test.getAsJsonObject("memory").entrySet())
                    emu.writeMemory(address(e.getKey()),bytes(e.getValue().getAsString()));
                int steps=test.has("steps")?test.get("steps").getAsInt():1;
                for(int n=0;n<steps;n++) {
                    if(!emu.step(monitor)) throw new Exception(emu.getLastError());
                    emu.setContextRegister(currentProgram.getRegister("ISA_MODE"),BigInteger.valueOf(isaMode[0]));
                }
                JsonObject registers=new JsonObject();
                // Sleigh may retain a backing write to zero (e.g. JALR rd=0).
                // Architecturally GPR0 is hardwired zero; normalize that view.
                for(String register:REGS) registers.addProperty(register,String.format("%08x",register.equals("zero")?0L:emu.readRegister(register).longValue()&0xffffffffL));
                registers.addProperty("hi",String.format("%08x",emu.readRegister("hi").longValue()&0xffffffffL));
                registers.addProperty("lo",String.format("%08x",emu.readRegister("lo").longValue()&0xffffffffL));
                result.add("regs",registers);
                result.addProperty("pc",String.format("%08x",emu.getExecutionAddress().getOffset()));
                result.addProperty("isa_mode",isaMode[0]);
                if(test.has("read_ranges")) {
                    JsonObject memory=new JsonObject();
                    for(JsonElement range:test.getAsJsonArray("read_ranges")) {
                        JsonObject r=range.getAsJsonObject();String a=r.get("address").getAsString();
                        memory.addProperty(a,java.util.HexFormat.of().formatHex(emu.readMemory(address(a),r.get("length").getAsInt())));
                    }
                    result.add("memory",memory);
                }
                result.addProperty("status","ok");
            } catch(Exception e) { result.addProperty("status","error");result.addProperty("error",e.toString()); }
            finally { emu.dispose(); }
            output.add(result);
        }
        Files.writeString(Path.of(getScriptArgs()[1]),new GsonBuilder().setPrettyPrinting().create().toJson(output)+"\n");
        println("Oracle cases: "+output.size());
    }
}
