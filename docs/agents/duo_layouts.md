# iPhone Duo layout reference

Use these names when discussing layouts and naming screenshots. Dimensions are
browser viewport sizes in CSS pixels, excluding the simulator frame.

| Layout | Screen and orientation | Reference viewport |
| --- | --- | --- |
| Duo Closed Portrait | Outer screen, upright | Not yet confirmed |
| Duo Closed Landscape | Outer screen, horizontal | 696 × 464 |
| Duo Open Portrait | Inner screen, vertical | 696 × 976 |
| Duo Open Landscape | Inner screen, horizontal | 976 × 696 |

Add **Camera Left** or **Camera Right** to distinguish the two closed landscape
rotations. Add **Status Left** or **Status Right** when the position of the iOS
status controls matters on the open screen. For example:

- Duo Closed Landscape — Camera Right
- Duo Open Portrait — Status Right

## Layout expectations

- Closed Landscape shows the top portion of Open Portrait at the same width.
  Media details keep the same backdrop and logo geometry as the taller view;
  metadata and actions remain farther down the scrollable page.
- Leave space below the logo before the fold or bottom edge.
- Keep navigation and iOS status controls on the same row. Respect a camera
  inset on the left; a bottom-right camera does not require extra right padding
  in the top navigation. Content still respects its safe-area insets.
- Use available width for compact information rows and left-aligned cards.
  A shorter viewport should not make the cards taller.
- Check all three confirmed viewports, both closed landscape rotations, and
  desktop widths when changing shared responsive styles. Desktop checks should
  account for the space taken by the sidebar.
- Browser resizing validates layout geometry. Native camera and status insets
  also require simulator checks or explicit inset emulation.

## Safari side-rail paint

Safari 27.1 can report a narrower layout viewport than the display even with
`viewport-fit=cover`: the closed portrait simulator measured `screen.width =
466`, `innerWidth = clientWidth = visualViewport.width = 382`, at scale 1 and
visual viewport offset 0. The remaining 84px is decorative paint space, not
additional room for application controls.

`static/js/safari-rail.js` adds an aria-hidden column outside `.app-shell` only
for touch iPhone Safari with a measured 40–200px gap. Standalone mode is excluded.
The shell retains its width. The column carries the page background, a
scroll-timeline-driven copy of the header background/border/shadow. The original
mobile hero's backdrop wrapper grows equally left and right so its centre stays
on the safe area while the right side reaches the rail. Its logo and content keep
their original geometry. No artwork is cloned or mirrored. Resizing and HTMX
navigation refresh the column. Pinch zoom restores horizontal panning.
The sidebar scrim also paints in document space across both widths, keeping its
50% dimming and click-to-close behavior without Safari's opaque fixed-layer tint.

Safari's collapsing toolbar changes `innerHeight` while `clientHeight` stays
fixed; the header's scroll range must use `innerHeight` to remain aligned.
Do not replace the column with fixed overflow or clip the whole app: Safari
needs actual document overflow to paint the rail. The technique comes from
[Offform's simulator investigation](https://www.offform.design/designing-websites-for-iphone-duo-how-we-made-our-framer-sites-go-edge-to-edge/).

`app.tests.test_safari_rail_browser` covers layout preservation, browser/mode
guards, resizing, theme changes, deferred hero arrival and navigation away.
These Chromium geometry tests cannot validate Safari's native rail compositing;
check it in Device Hub as well.
