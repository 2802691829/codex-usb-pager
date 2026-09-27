# Blossom Buzzer Service Cavity Design

Date: 2026-07-29

## Goal

Replace the buzzer-matched cylindrical relief with a substantially larger
service cavity in the left rear Blossom petal. The cavity must maximize usable
assembly space without changing the visible enclosure exterior.

## Approved Geometry

- Keep the buzzer validation envelope at 12.0 mm diameter and 11.5 mm height.
- Remove the buzzer envelope's cylindrical shape as the production cavity
  boundary.
- Create a connected service cavity that opens from the existing rectangular
  electronics cavity into the left Blossom petal.
- Start the service cavity at the PCB/buzzer front plane, Z = 4.30 mm.
- Extend it to Z = 18.30 mm, the safe inner rear surface, instead of stopping
  at the buzzer's 11.5 mm validation height.
- Define its generous pre-clipping window as X = -28.0 to -12.0 mm and
  Y = -5.5 to 18.0 mm. This overlaps the existing electronics cavity by
  2.0 mm and leaves the lower latch and upper locator outside the window.
- Give the pre-clipping window 3.0 mm corner radii.
- Expand the cavity toward the left petal as far as the protected inner
  Blossom contour permits.
- Preserve at least 1.50 mm of exterior wall and relief backing around the new
  cavity.
- Keep the service cavity clear of the upper locator tongue/socket pair and
  the lower hidden spring latch and its activity tunnel.
- Use rounded transitions where the service cavity joins the existing
  electronics cavity. No buzzer-shaped circular wall is retained.

## Closure Features

The small raised feature and matching recess shown near the upper shell edge
are the front-shell locator tongue and rear-shell locator socket. They prevent
upper-edge shear, rocking, and assembly misalignment. The side spring latches
remain responsible for locking the enclosure.

Both upper locators remain unchanged and hidden after assembly.

## Exterior Contract

The following visible geometry must remain unchanged:

- 56.0 mm Blossom outer width and unwarped SVG proportion.
- Front and rear 1.5 mm Blossom relief.
- Front screen hexagon and screen pocket alignment.
- Rear rounded USB opening.
- Continuous front and rear exterior surfaces with no buzzer opening.

The service cavity cutter is clipped to an internal protected Blossom core.
It must not intersect the exterior guard.

## Mechanical Keepouts

The new cavity must not obstruct:

- the 26.30 x 29.30 mm screen pocket and its retainers;
- the four screen locating posts;
- the two upper tongue/socket locators;
- the two lower hidden spring latches and their motion envelopes;
- the USB adapter window and support structure.

## Verification

Automated checks must prove:

- buzzer service cavity exterior breach volume is 0.0 mm3;
- buzzer obstruction volume remains 0.0 mm3;
- closure, USB, screen, and assembly interference volumes remain 0.0 mm3;
- the rear shell remains valid and a single solid;
- front and rear exterior dimensions and relief depths are unchanged;
- the new service cavity is wider and deeper than the 12.0 x 11.5 mm buzzer
  validation envelope;
- rendered rear-inside and assembly-cutaway views visibly show the enlarged
  non-cylindrical cavity;
- front and rear exterior renders remain visually unchanged.

## Deliverables

- Updated FreeCAD source model.
- Regenerated FCStd, STEP, front STL, and rear STL files.
- Updated geometry audit and regression tests.
- Updated review renders and a refreshed handoff archive.
