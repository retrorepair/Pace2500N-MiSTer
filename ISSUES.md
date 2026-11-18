# Issues log

Open issues to come back to. Newest first. Each entry: what is seen, where, and any thoughts so far.

## Widescreen-on-4:3 option double-boxes pillarboxed programmes (reported 18 Nov 2026)

- **Seen:** the OSD option *Widescreen on 4:3* (Letterbox) letterboxes 16:9 pictures correctly.
  But much 16:9 material is itself 4:3 content pillarboxed for 16:9 TVs (black bars left and
  right inside the 16:9 frame). Letterboxing that gives the right height but black bars on all
  four sides ("windowboxed").
- **Where:** the letterbox path of the MPEG video output (OSD status bit 6, `letterbox`, through
  rtl/pace_ts_stream.sv / the decoder scaler), and the playout's per-programme aspect handling.
- **Ideas (not decided):** a zoom/crop option; or detecting the pillarbox bars (playout side, from
  the source's active picture area or a crop-detect pass when transcoding) and sending such
  programmes as 4:3 full-frame so the box shows them without bars. Needs a decision with the user.
- **Status:** for later.
