"""Render the Task 6 four-latch retrofit review set."""

from __future__ import annotations

from collections import Counter
import math
import os

import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from PySide import QtCore, QtGui, QtWidgets


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENCLOSURE_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(ENCLOSURE_DIR, "outputs", "four-latch-retrofit")
DOCUMENT_PATH = os.path.join(OUTPUT_DIR, "blossom-enclosure.FCStd")
IMAGE_WIDTH = 1600
IMAGE_HEIGHT = 1200
RENDER_ASPECT_RATIO = IMAGE_WIDTH / IMAGE_HEIGHT
CAMERA_MARGIN = 1.35
FRAME_MARGIN_PX = 16
MAX_RENDER_ATTEMPTS = 2


CAMERA_DIRECTIONS = {
    "top": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    "bottom": ((0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    "front": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "axonometric": ((-1.0, 1.0, -1.0), (0.0, 0.0, 1.0)),
}


RENDER_HELPERS = {}


VIEWS = {
    "review-front-exterior.png": (
        ("FrontShell",),
        "bottom",
    ),
    "review-rear-exterior.png": (
        ("RearCover",),
        "top",
    ),
    "review-front-inside.png": (
        ("FrontShell",),
        "top",
    ),
    "review-rear-inside.png": (
        (
            "RearCover",
            "RearScreenSupport",
            "RearScreenEdgeStop1",
            "RearScreenEdgeStop2",
            "RearScreenEdgeStop3",
            "RearScreenEdgeStop4",
            "RearUpperSocketLeft",
            "RearUpperSocketRight",
            "RearLowerGuideLeft",
            "RearLowerGuideRight",
            "RearLowerDetentLeft",
            "RearLowerDetentRight",
        ),
        "bottom",
    ),
    "review-screen-setback-section.png": (
        (
            "FrontShell",
            "RearCover",
            "ScreenFaceEnvelope",
            "RearScreenSupport",
        ),
        "front",
    ),
    "review-four-latch-cutaway.png": (
        (
            "FrontUpperTabLeft",
            "RearUpperSocketLeft",
            "FrontLowerTabLeft",
            "RearLowerGuideLeft",
            "RearLowerDetentLeft",
        ),
        "axonometric",
    ),
    "review-assembly-1-tilted.png": (("AssemblyPoseTilted",), "axonometric"),
    "review-assembly-2-flat.png": (("AssemblyPoseFlatUnlocked",), "axonometric"),
    "review-assembly-3-locked.png": (("AssemblyPoseLocked",), "axonometric"),
    "review-usb-shift.png": (("RearCover", "UsbWindow"), "front"),
}


MIN_CONTENT_AREA_FRACTION = {
    filename: (
        0.03
        if "four-latch" in filename
        else 0.10
        if "assembly" in filename
        else 0.15
    )
    for filename in VIEWS
}


STYLE = {
    "FrontShell": ((0.72, 0.76, 0.80), 0),
    "RearCover": ((0.42, 0.46, 0.50), 0),
    "ScreenFaceEnvelope": ((0.25, 0.75, 0.92), 70),
    "RearScreenSupport": ((0.20, 0.72, 0.34), 0),
    "RearScreenEdgeStop1": ((0.98, 0.78, 0.18), 0),
    "RearScreenEdgeStop2": ((0.98, 0.78, 0.18), 0),
    "RearScreenEdgeStop3": ((0.98, 0.78, 0.18), 0),
    "RearScreenEdgeStop4": ((0.98, 0.78, 0.18), 0),
    "FrontUpperTabLeft": ((0.18, 0.48, 0.95), 0),
    "FrontLowerTabLeft": ((0.18, 0.48, 0.95), 0),
    "RearUpperSocketLeft": ((0.95, 0.20, 0.20), 68),
    "RearUpperSocketRight": ((0.95, 0.20, 0.20), 68),
    "RearLowerGuideLeft": ((0.95, 0.20, 0.20), 68),
    "RearLowerGuideRight": ((0.95, 0.20, 0.20), 68),
    "RearLowerDetentLeft": ((0.72, 0.20, 0.82), 62),
    "RearLowerDetentRight": ((0.72, 0.20, 0.82), 62),
    "AssemblyPoseTilted": ((0.72, 0.76, 0.80), 0),
    "AssemblyPoseFlatUnlocked": ((0.72, 0.76, 0.80), 0),
    "AssemblyPoseLocked": ((0.72, 0.76, 0.80), 0),
    "UsbWindow": ((0.20, 0.72, 0.34), 45),
}


def create_render_helpers(document) -> None:
    """Create unsaved sections derived from the audited Task 2 solids."""
    for name, (source_name, base, size) in RENDER_HELPERS.items():
        source = document.getObject(source_name)
        if source is None:
            raise KeyError(f"Missing helper source object: {source_name}")
        clip = Part.makeBox(*size, App.Vector(*base))
        section = source.Shape.common(clip)
        if section.isNull():
            raise ValueError(f"Empty review helper: {name}")
        helper = document.addObject("Part::Feature", name)
        helper.Label = name
        helper.Shape = section
    document.recompute()


def style_object(document, name: str) -> None:
    obj = document.getObject(name)
    if obj is None or obj.ViewObject is None:
        raise KeyError(f"Missing review object: {name}")
    color, transparency = STYLE.get(name, ((0.85, 0.85, 0.85), 0))
    obj.ViewObject.ShapeColor = color
    obj.ViewObject.LineColor = tuple(max(0.0, component - 0.28) for component in color)
    obj.ViewObject.LineWidth = 2.0
    obj.ViewObject.Transparency = transparency
    obj.ViewObject.Visibility = True


def flush_gui_events() -> None:
    """Drain both FreeCAD and Qt queues so the next render sees this state."""
    Gui.updateGui()
    application = QtWidgets.QApplication.instance()
    if application is not None:
        application.processEvents()
        application.sendPostedEvents()
        Gui.getMainWindow().repaint()
        application.processEvents()
    Gui.updateGui()


def hide_objects(document) -> None:
    for obj in document.Objects:
        if obj.ViewObject is not None:
            obj.ViewObject.Visibility = False


def show_objects(document, names) -> None:
    for name in names:
        style_object(document, name)


def assert_visible_objects(document, names) -> None:
    expected = set(names)
    actual = {
        obj.Name
        for obj in document.Objects
        if obj.ViewObject is not None and obj.ViewObject.Visibility
    }
    if actual != expected:
        raise RuntimeError(
            f"Visible review objects differ: expected={sorted(expected)} "
            f"actual={sorted(actual)}"
        )


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 1e-9:
        raise ValueError(f"Cannot normalize a zero vector: {vector}")
    return tuple(component / length for component in vector)


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def visible_shape_bounds(document, names):
    """Return the union bounds and corners of exactly the rendered solids."""
    boxes = []
    for name in names:
        obj = document.getObject(name)
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            raise KeyError(f"Missing rendered shape: {name}")
        boxes.append(obj.Shape.BoundBox)
    bounds = (
        min(box.XMin for box in boxes),
        min(box.YMin for box in boxes),
        min(box.ZMin for box in boxes),
        max(box.XMax for box in boxes),
        max(box.YMax for box in boxes),
        max(box.ZMax for box in boxes),
    )
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    corners = tuple(
        (x, y, z)
        for x in (xmin, xmax)
        for y in (ymin, ymax)
        for z in (zmin, zmax)
    )
    return bounds, corners


def configure_camera(document, view, names, direction) -> None:
    """Set every orthographic camera field from the visible-shape bounds."""
    if direction not in CAMERA_DIRECTIONS:
        raise KeyError(f"Unknown camera direction: {direction}")
    bounds, corners = visible_shape_bounds(document, names)
    look, up_hint = CAMERA_DIRECTIONS[direction]
    look = _normalize(look)
    right = _normalize(_cross(look, up_hint))
    up = _normalize(_cross(right, look))
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    target = (
        (xmin + xmax) * 0.5,
        (ymin + ymax) * 0.5,
        (zmin + zmax) * 0.5,
    )
    relative = tuple(
        tuple(corner[index] - target[index] for index in range(3))
        for corner in corners
    )
    horizontal = tuple(_dot(corner, right) for corner in relative)
    vertical = tuple(_dot(corner, up) for corner in relative)
    depth = tuple(_dot(corner, look) for corner in relative)
    projected_width = max(horizontal) - min(horizontal)
    projected_height = max(vertical) - min(vertical)
    projected_depth = max(depth) - min(depth)
    framing_height = max(
        projected_height,
        projected_width / RENDER_ASPECT_RATIO,
        0.01,
    )
    scene_span = max(
        projected_width,
        projected_height,
        projected_depth,
        1.0,
    )
    distance = scene_span * 4.0
    position = tuple(
        target[index] - look[index] * distance for index in range(3)
    )
    camera = view.getCameraNode()
    if not isinstance(camera, coin.SoOrthographicCamera):
        raise TypeError(
            f"Expected an orthographic camera, got {camera.getTypeId().getName()}"
        )
    camera.position.setValue(coin.SbVec3f(*position))
    camera.pointAt(coin.SbVec3f(*target), coin.SbVec3f(*up))
    camera.nearDistance.setValue(0.1)
    camera.farDistance.setValue(distance + scene_span * 2.0)
    camera.focalDistance.setValue(distance)
    camera.height.setValue(framing_height * CAMERA_MARGIN)


def validate_rendered_image(output_path, filename):
    """Reject blank, undersized or frame-clipped output after every save."""
    image = QtGui.QImage(output_path)
    if image.isNull():
        raise RuntimeError(f"Review image cannot be decoded: {output_path}")
    if image.width() != IMAGE_WIDTH or image.height() != IMAGE_HEIGHT:
        raise RuntimeError(
            f"Review image has wrong dimensions: {filename} "
            f"{image.width()}x{image.height()}"
        )
    sample_points = (
        (0, 0),
        (image.width() - 1, 0),
        (0, image.height() - 1),
        (image.width() - 1, image.height() - 1),
    )
    background = Counter(
        image.pixel(x, y) for x, y in sample_points
    ).most_common(1)[0][0]
    mask = image.createMaskFromColor(background, QtCore.Qt.MaskInColor)
    rect = QtGui.QRegion(QtGui.QBitmap.fromImage(mask)).boundingRect()
    if rect.isNull():
        raise RuntimeError(f"Review image is blank: {filename}")
    if (
        rect.left() < FRAME_MARGIN_PX
        or rect.top() < FRAME_MARGIN_PX
        or rect.right() >= image.width() - FRAME_MARGIN_PX
        or rect.bottom() >= image.height() - FRAME_MARGIN_PX
    ):
        raise RuntimeError(
            f"Review image content touches the frame: {filename} "
            f"bbox=({rect.left()},{rect.top()},{rect.right() + 1},"
            f"{rect.bottom() + 1})"
        )
    content_fraction = (
        rect.width() * rect.height() / (image.width() * image.height())
    )
    minimum_fraction = MIN_CONTENT_AREA_FRACTION[filename]
    if content_fraction < minimum_fraction:
        raise RuntimeError(
            f"Review image content area is too small: {filename} "
            f"fraction={content_fraction:.4f} minimum={minimum_fraction:.4f}"
        )
    return (
        rect.left(),
        rect.top(),
        rect.right() + 1,
        rect.bottom() + 1,
    )


def render_view(document, view, filename, names, direction) -> None:
    hide_objects(document)
    flush_gui_events()
    show_objects(document, names)
    flush_gui_events()
    output_path = os.path.join(OUTPUT_DIR, filename)
    last_error = None
    for attempt in range(MAX_RENDER_ATTEMPTS):
        configure_camera(document, view, names, direction)
        flush_gui_events()
        assert_visible_objects(document, names)
        view.saveImage(
            output_path,
            IMAGE_WIDTH,
            IMAGE_HEIGHT,
            "Current",
        )
        flush_gui_events()
        try:
            validate_rendered_image(output_path, filename)
            return
        except RuntimeError as error:
            last_error = error
            if attempt + 1 < MAX_RENDER_ATTEMPTS:
                view.setCameraType("Orthographic")
                view.setAnimationEnabled(False)
                flush_gui_events()
    raise RuntimeError(
        f"Review render failed after {MAX_RENDER_ATTEMPTS} attempts: "
        f"{filename}: {last_error}"
    )


def render() -> None:
    if not os.path.exists(DOCUMENT_PATH):
        raise FileNotFoundError(DOCUMENT_PATH)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    document = App.openDocument(DOCUMENT_PATH)
    Gui.ActiveDocument = Gui.getDocument(document.Name)
    gui_document = Gui.ActiveDocument
    if gui_document is None:
        raise RuntimeError("FreeCAD GUI document is unavailable")
    view = gui_document.activeView()
    create_render_helpers(document)
    flush_gui_events()
    view.setCameraType("Orthographic")
    view.setAnimationEnabled(False)
    flush_gui_events()

    for filename, (names, direction) in VIEWS.items():
        render_view(document, view, filename, names, direction)

    App.closeDocument(document.Name)
    print("RENDER PASS", OUTPUT_DIR)


def close_renderer_window() -> None:
    """Close a dedicated macro window after the reusable render has returned."""
    application = QtWidgets.QApplication.instance()
    Gui.getMainWindow().close()
    flush_gui_events()
    if application is not None:
        application.quit()
        flush_gui_events()


if __name__ == "__main__":
    try:
        render()
    finally:
        close_renderer_window()
