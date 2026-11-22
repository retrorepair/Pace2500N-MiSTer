# Live Teletext and page 888 subtitles

V080B and Channel Builder0.8.0B add a live text service to the existing RGB/SCART
output. Firmware CPU execution remains entirely in FPGA. The PC supplies the
broadcast data, as it already supplies A/V and EPG. V080A remains the fallback.

Use the TV's own Text/page-number controls:

| Page | Contents |
| --- | --- |
|100|Index|
|101|Live receiver test with a changing clock|
|200 onward|The configured channels' actual now/next listings, four per page|
|300|BBC News headlines|
|400|Weather for the approximate public-IP location|
|500|Recent official MiSTer Main commits|
|888|English subtitles when a usable source track exists|

The core OSD has **Live Teletext: On/Off**, defaultOn. The original fixed page100
fixture remains available with F11 for30s; live packets resume afterwards.
Switch back to ordinary TV viewing when using888 as a subtitle overlay. Actual
TV overlay behaviour and timing need checking on the physical display.

Channel Builder Settings contains switches for live Teletext, subtitles,
internet pages and automatic pillarbox removal. Subtitle delay is configurable
from-10 to+10seconds (initial0.7); positive values delay captions. These settings
belong to this app; Plex's general track preferences are unchanged.

## Sources and limits

Plex external/embedded SRT and other FFmpeg-readable text subtitle tracks are
converted to timed page888 cues. IPTV can supply separate text tracks such as
WebVTT or existing DVB Teletext subtitles; the latter are copied and remapped to
888. **No OCR** is performed. Image-only PGS/VobSub/DVB bitmap subtitles and
burned-in-only captions are not converted to text. Foreign-language text is not
substituted for an English image track. A real Red Dwarf sample has English PGS
and Czech SRT, so it needs an English text track for888 under this policy.

Subtitle queues are bounded and extraction is independent of A/V. Cues are
normalised from HLS WebVTT timestamp maps (including33-bit MPEGTS wrap) when
FFmpeg advertises a text rendition but does not emit its packets. The text
rendition is then read directly under [RFC8216](https://www.rfc-editor.org/rfc/rfc8216).
Cue times are mapped against the probed video start timestamp. Cues are
selected against the transport output clock and source seek, cleared at their
end, and replaced on retune/programme change. Live IPTV copy timing and actual
TV display latency still need measurement; use the delay setting if necessary.

Feeds refresh in a background thread every10minutes. Failures retain the last
successful page with its fetch time, or show an unavailable message. News uses
[BBC RSS](https://feeds.bbci.co.uk/news/rss.xml); page500 describes official
[Main_MiSTer commits](https://github.com/MiSTer-devel/Main_MiSTer/commits/master/),
not a separately curated MiSTer news bulletin.

Weather uses the PC connection's public egress IP via
[ipwho.is](https://ipwhois.io/documentation), then
[Open-Meteo](https://open-meteo.com/en/docs). This is an approximate ISP/VPN
location, not the router's private LAN address. It needs no API key. Optional
`teletext_weather_location` in app settings can override it with a JSON object
containing`latitude`,`longitude`,`city`. No public IP is logged in feed messages.

## Filling pillarboxed 4:3 video

For scheduled files/Plex, three separated video samples must agree that a16:9
source contains a centred4:3 picture with sustained black side bars and full
height. Only then is that rectangle cropped before normal PAL scaling. Genuine
wide content retains the existing letterbox behaviour. Results are cached and
prepared in the background for current scheduled titles; an uncached title may
need a retune or next programme start after analysis completes. Live IPTV is not
subjected to scene-dependent automatic cropping in this revision.

An actual Red Dwarf Blu-ray source was detected as1440x1080 at x240,y0 inside
1920x1080. The same crop fills720x576 with PAL4:3 sample aspect16:15.

## Implementation and validation

The server multiplexes bounded EN300472 Teletext PES on PID0x1EF0, advertised by
descriptor0x56. A passive FPGA tap validates the PC's canonical one-TS-packet
PES format, reserves FIFO space atomically, crosses to54MHz video, and emits raw
SystemB lines during blanking. It does not stall A/V or replace firmware CPU
execution. This bridge does not claim to emulate the EMMA B0008xxx controller or
accept arbitrary DVB PES directly; IPTV is normalised on the PC first.

The existing electrical levels, PDM pedestal, sync timing and RGB/VS signals
remain unchanged. Live output uses blanking lines8–18 relative to field start,
up to550lines/s; the PC is capped at360lines/s. The FIFO is cleared on stream
changes and while the fixed fixture owns the output, preventing stale cues.

Tests: real FFmpeg SRT extraction/seek/shutdown and pillarbox detection; language,
cue boundary, packet and mux tests; malformed-PES/overflow admission; full
TS-to-VBI simulation across two clocks, all60 output lines byte-identical to
input; independent libzvbi decoding of100 and888, including boxed captions and
transparent background. Fixed-test controls also pass with live-mode FIFO reset
feedback enabled. All49 saved channels load and HTTP transport includes Teletext.
Quartus and on-hardware results are recorded in the latest handoff; simulator
results alone do not establish physical-TV timed-subtitle success.

The portable app copy is`C:\Pace2500N\PaceChannelBuilder.exe`. Windows may ask
for firewall permission for that relocated copy; handle its security prompt
yourself. This session updated the existing authorised app location and verified
that MiSTer could reach it, without changing Windows firewall settings. Existing
media folders/settings remain in use; this is not a migration of the ROM library.
