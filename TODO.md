Must-Have                                                                                  
                                                                                             
  - Smart Preloading for Adjacent Scenes — Preload linked scenes in the background for       
  near-instant transitions in tours                                                          
  - Accessibility Improvements — ARIA labels, keyboard-navigable hotspots, screen reader
  support, WCAG 2.1 compliance                                                               
                                                                                             
  Quick Wins (low effort, high value)                                                        
                                                                                             
  - Keyboard Shortcuts Help Overlay — Press "?" to see all controls (~50 lines)              
  - Gyroscope Calibration UI — Reset "forward" direction on mobile (~60 lines)
  - Hotspot Animation Effects — Pulse, bounce, fade-in via CSS keyframes (mostly CSS)
  - Screenshot / Export Current View API — getScreenshot() using canvas.toDataURL() (~90
  lines)
  - Lazy Load Hotspots — Destroy/recreate hotspot DOM on scene change for large tours (~20
  line refactor)
  - Batch Hotspot Operations API — addHotSpots(), removeHotSpots(), updateHotSpot() (~80
  lines)
  - Custom Loading Indicator — Callback/template for branded loading UI (~40 lines)

  Medium Effort

  - Minimap / Thumbnail Navigator — Clickable scene thumbnails for tour navigation
  - NPM Package with ES Modules — Modern import/export, tree-shaking, TypeScript declarations
  - Error Recovery / Retry Mechanism — Auto-retry failed tile loads with exponential backoff
  - Performance Monitoring API — FPS, tile load times, memory usage overlay + API

  Larger Features

  - Annotation Mode / Drawing Tools — Freehand drawing on panoramas with serialization for
  collaboration
  - Multi-Resolution Generator Web UI — Drag-and-drop web interface for generate.py

  The agent also found two existing TODO comments in pannellum.js (lines 619 and 880) worth
  investigating, and noted potential modernization opportunities: TypeScript definitions,
  Node-based build tooling, and unit test coverage.