# Pace2500S5 comparison reference

User-supplied source:
https://drew1440.com/2021/03/02/inside-a-pace-2500s5-digibox/

The article identifies an STi5512/ST20 main processor, so this board is a
different platform from the NEC2500N target. CPU, memory maps, video registers
and tuner programming must not be transferred from it without independent proof.

The full-resolution close-up clearly identifies a separate MicrochipPIC16F74
at U1200, despite the article's uncertainty about its role:
https://drew1440.com/wp-content/uploads/2021/02/dsc_1189.jpg

This is a useful comparison lead for the2500N's external peripheral/watchdog
controller. It does not establish the2500N controller's part number, firmware,
command protocol or reset behavior. Target-specific documentation names its
watchdog controller U1300. Check this lead against the genuine NEC serial driver
and reset path; no hardware-model behavior has been changed on this evidence.

Downloaded comparison images are under `re/reference_comparison/` and are
labelled2500S5 throughout. The sealed1416 checkpoint ZIP remains unchanged.
