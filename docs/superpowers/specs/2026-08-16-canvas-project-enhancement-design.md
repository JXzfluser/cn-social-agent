# Canvas and Project Workspace Enhancement

## Goal

Turn the knowledge canvas and project board from utility views into a coherent editorial workspace: reliable in-app editing, visible directional relationships, faster spatial navigation, richer project status, and direct handoff between projects and canvases.

## Design decisions

### Shared interaction language

- Replace browser `prompt()` / `confirm()` calls with one accessible workbench dialog for create, rename, delete, edge labels, and reject reasons.
- Keep the warm editorial visual language already used by the workbench.
- Secondary actions stay quiet; destructive actions use explicit confirmation and red treatment.
- Keyboard and pointer interactions must have equivalent button/menu actions.

### Knowledge canvas

1. **Directional edges**
   - Compute line endpoints at node rectangle boundaries rather than node centers.
   - Render smooth cubic curves with arrow markers outside node content.
   - Double-click an edge to edit its label; deletion is available in the same dialog.

2. **Navigation**
   - Add “fit content” and a bottom-right minimap.
   - The minimap shows the viewport and supports click-to-navigate.

3. **Creation and manipulation**
   - Double-click empty canvas space to create a note.
   - Add a node context menu: connect, duplicate, complete, recolor, delete.
   - Preserve existing marquee selection, drag, resize, undo/redo, and autosave.

4. **Templates**
   - New boards may start blank or from: topic funnel, script structure, SWOT.
   - Templates are normalized through the existing canvas model and saved as ordinary nodes/edges.

5. **AI organize**
   - Add a guarded “AI organize” action for selected nodes.
   - It returns normalized node updates and optional edges; it never publishes content.
   - If no configured LLM is available, return a clear error without changing the canvas.

### Project board

1. **Find and prioritize**
   - Search by topic and source.
   - Filter by category and artifact state.
   - Sort by updated time, created time, or evidence count.

2. **Readable progress**
   - Cards show compact evidence, canvas, journal/card, presentation, and video indicators.
   - Quality state and reject reason remain visible.

3. **Direct manipulation**
   - Cards can be dragged between candidate, active, and export-ready lanes.
   - Rejected remains a deliberate action because it requires a reason.

4. **Project detail drawer**
   - Clicking a card opens a right-side drawer with overview, source, evidence, canvas, artifacts, quality, and timestamps.
   - Primary actions open the project canvas or relevant workshop.

5. **Project–canvas continuity**
   - “Open canvas” always opens the project-bound canvas.
   - Canvas handoff continues to write the resulting artifact association to the active project where supported.

## Architecture

- Put pure geometry, filtering, sorting, and template logic in focused modules so they can be unit-tested without a browser.
- Keep HTTP routes thin and reuse existing Content Project and canvas persistence.
- Split new front-end behavior into `canvas_enhancements.js` and `project_board.js`, loaded by the existing workbench, instead of growing the inline script further.
- Use the existing `api()` wrapper and authenticated routes.

## Error handling

- Invalid board/project IDs produce visible workbench errors.
- Failed autosave keeps the dirty state and never replaces local in-memory nodes.
- Invalid edge endpoints are discarded by normalization.
- Drag-to-lane reverts visually if the API move fails.
- AI organization is opt-in and applies only after a successful normalized response.

## Testing

- Unit tests for rectangle-edge intersection, curve paths, templates, project filtering/sorting, and progress summaries.
- Route tests for templates and AI organization validation.
- Existing canvas/project persistence tests remain green.
- Browser smoke test: create/rename modal, arrows, label editing, fit/minimap, template creation, board filters, drawer, drag-to-lane, project-to-canvas handoff.

## Out of scope

- Real-time multi-user collaboration.
- Infinite canvas virtualization.
- Auto-publishing.
- Arbitrary graph layout engines or new front-end frameworks.
