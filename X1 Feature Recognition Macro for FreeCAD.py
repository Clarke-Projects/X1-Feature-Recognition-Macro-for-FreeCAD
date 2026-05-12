#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
x1_2026_r20b_guarded_missing_bore_promotion.py
=========================

FreeCAD macro: X1_2026 R20B guarded tessellated promotion preview for stable CAD-like bores, FAST layer stacks, diagnostic axis-side probes, and preview-only restoration cylinders.

R8 is built from the proven R5/R6/R7 stable baseline.
It keeps the successful wire/inner-wire detector unchanged and adds a guarded
visual marker mode for only the strongest clustered missing-pocket regions, with marker orientation inferred from nearby accepted bore context when safe.
It does not emit R4-style individual weak pocket probes.

R3 was a corrective version after the first X1 tests produced random-looking
large, shallow cylinders.  The reason was that the old discrete scanner fitted
circles through arbitrary point slices.  Those slices can describe outside
silhouettes or surface bands instead of real bore openings.

The accepted-feature path still uses the stricter CAD-style rule:

    An accepted bore candidate must come from real closed circular wires,
    inner face wires, analytic circles, or analytic cylindrical faces.

R20B keeps the R19A/R19B/R20B accepted-feature path and consolidated evidence ledger unchanged, preserves Tier A/Tier B review markers, and adds guarded promotion-preview cylinders for strong tessellated candidates. These preview cylinders are diagnostic only and are not promoted to accepted bores.

The macro is still one single file.  It keeps the useful folder/group output and
axis colors:

    X -> red
    Y -> green
    Z -> blue
    FREE/angled -> yellow

How to use
----------
1. Open FreeCAD.
2. Select one or more objects with a Shape.
3. Run this file as a macro or execute it as a .py file in FreeCAD.
4. Inspect the group X1_2026_R20B_Feature_Tree. The conservative R18A/R18B accepted-bore path remains unchanged. R20B keeps the R18I/R18J/R19A diagnostics, keeps diagnostic-only tessellated review markers, and adds preview-only promotion cylinders under the consolidated ledger tree. These preview cylinders make strong side-pair evidence visible without promoting it to accepted features.

Design notes
------------
- This is conservative.  It should prefer zero cylinders over random cylinders.
- It is meant as a working macro first, not as a separated library yet.
- The code is structured in sections so it can later be split cleanly.
"""

import math
import traceback
import time
import os
import json
import csv

try:
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part
except Exception:
    App = None
    Gui = None
    Part = None


# =============================================================================
# User configuration
# =============================================================================

X1_VERSION = "X1_2026_R20B_guarded_missing_bore_promotion"
X1_OUTPUT_GROUP_NAME = "X1_2026_R20B_Feature_Tree"

# Main acceptance threshold.  Keep conservative while debugging.
X1_MIN_CONFIDENCE = 0.45

# Visual output.
X1_CYLINDER_TRANSPARENCY = 65
X1_CYLINDER_OVERLAP = 0.25
X1_COPY_SOURCE_PLACEMENT_TO_OUTPUT = True

# Debug visuals.  These are off by default to keep the scene clean.
X1_CREATE_DEBUG_RINGS = False
X1_CREATE_REJECTED_POINTS = False

# Circle/wire recognition.
X1_MIN_RING_POINTS = 6
X1_MAX_RING_REL_RMS = 0.070        # radial RMS / radius.  Lower = stricter.
X1_MAX_RING_PLANE_REL = 0.020      # plane thickness / radius for wire rings.
X1_PLANE_ABS_TOL = 0.030           # mm-ish fallback tolerance.
X1_MIN_RADIUS = 0.05
X1_MIN_DEPTH = 0.10
X1_RING_RADIUS_REL_TOL = 0.14
X1_CENTER_ABS_TOL = 0.80
X1_CENTER_RADIUS_FACTOR = 0.18
X1_AXIS_PARALLEL_DOT = 0.985

# Global closed wires can include outer object silhouettes.  They are weaker
# than analytic circles or face-inner wires.  This guard rejects obvious huge
# unknown rings unless there is stronger analytic/inner-wire confirmation.
X1_UNKNOWN_RING_MAX_CROSS_SECTION_FRACTION = 0.36

# Tessellated ring-stack support.  With no analytic cylinder face, require at
# least two separated rings.  One closed ring is only an opening, not a cylinder.
X1_MIN_RINGS_WITHOUT_CYL_FACE = 2
X1_MIN_INNER_OR_ANALYTIC_RINGS_FOR_WEAK_STACK = 1

# Printing.
X1_PRINT_ACCEPTED_DETAILS = True
X1_PRINT_REJECTED_SUMMARY = True
X1_MAX_REJECTED_LINES = 12

# R5 policy: keep R3's good behavior and do not emit R4-style weak pocket probes.
# Missing-pocket work should be reintroduced only when a safe, confirmed rule exists.
X1_EMIT_WEAK_POCKET_PROBES = False

# R5 adds non-geometric feature/profile annotation.  This does not move, merge,
# resize, or add cylinders.  It only labels nearby coaxial multi-radius segments
# as possible stepped/counterbore/pocket stacks.
X1_ANNOTATE_STEPPED_STACKS = True
X1_PRINT_ACCEPTED_BREAKDOWN = True

# R7/R8/R9/R10/R11/R18G missing-pocket inspector.
# R7 printed ranked candidates and clustered physical regions from rejected one-ring groups.
# R8 can optionally emit only the strongest multi-wire pocket-region markers in a separate diagnostic subgroup.
# The accepted bore path remains R5.
X1_PRINT_MISSING_POCKET_DIAGNOSTICS = True
X1_MAX_POCKET_DIAGNOSTIC_LINES = 18
X1_POCKET_DIAGNOSTIC_MIN_SCORE = 1.50
X1_POCKET_DIAGNOSTIC_MAX_RADIUS_FRACTION = 0.18

# R7 addition: cluster many one-ring suspects into physical regions.
# This helps identify whether the missing pockets appear as repeated nearby
# weak wires without re-introducing R4's false-positive geometry.
X1_PRINT_POCKET_REGION_DIAGNOSTICS = True
X1_MAX_POCKET_REGION_LINES = 12
X1_POCKET_REGION_MIN_MEMBERS = 2
X1_POCKET_REGION_MIN_SCORE = 4.50
X1_POCKET_REGION_CLUSTER_ABS_TOL = 2.80
X1_POCKET_REGION_CLUSTER_RADIUS_FACTOR = 1.10


# R8 guarded visual confirmation of clustered pocket regions.
# This is NOT a bore acceptance path.  It emits separate translucent marker
# cylinders only for strong, multi-wire, single-axis pocket-region clusters.
# On the current reference part this should isolate the four repeated missing
# side-pocket regions instead of the 70 individual weak-wire fragments.
X1_EMIT_STRONG_POCKET_REGION_MARKERS = True
X1_MAX_STRONG_POCKET_REGION_MARKERS = 8
X1_STRONG_POCKET_REGION_MIN_MEMBERS = 6
X1_STRONG_POCKET_REGION_MIN_SCORE = 12.0
X1_STRONG_POCKET_REGION_MIN_DOMINANT_AXIS_COUNT = 5
X1_STRONG_POCKET_REGION_MAX_AXIS_MIX = 1
X1_STRONG_POCKET_REGION_MIN_RADIUS_FRACTION = 0.055
X1_STRONG_POCKET_REGION_MAX_RADIUS_FRACTION = 0.145
X1_STRONG_POCKET_REGION_MAX_SPREAD_ABS = 8.0
X1_STRONG_POCKET_REGION_MAX_SPREAD_RADIUS_FACTOR = 1.35
X1_POCKET_REGION_MARKER_HEIGHT_FACTOR = 0.85
X1_POCKET_REGION_MARKER_MIN_HEIGHT = 2.0
X1_POCKET_REGION_MARKER_MAX_HEIGHT = 6.0
X1_POCKET_REGION_MARKER_TRANSPARENCY = 80


# R9/R10 contextual marker orientation and sizing.
# R8 correctly found the four strong physical regions, but local weak wires can
# describe a side loop whose normal is not the true pocket/bore axis.  R9/R10 keeps
# the same region discovery but, for marker geometry only, asks whether the
# region sits on/near an already accepted bore line.  If yes, the diagnostic
# marker uses that accepted bore's axis and snaps its centerline to the bore
# line.  This is not a hard-coded X rule; it works for whichever accepted bore
# axis provides the best geometric context.
X1_R10_CONTEXT_AXIS_OVERRIDE_ENABLED = True
X1_R10_CONTEXT_CROSS_DISTANCE_FACTOR = 1.25
X1_R10_CONTEXT_PRIMITIVE_RADIUS_FACTOR = 2.60
X1_R10_CONTEXT_AXIAL_EXTRA_FACTOR = 1.60
X1_R10_CONTEXT_PRIMITIVE_AXIAL_FACTOR = 3.20
X1_R10_CONTEXT_MIN_SCORE_MARGIN = 0.0

# R20B sizing constants. Diagnostic-only marker sizing; stable accepted-bore path unchanged.
# They affect only the diagnostic pocket-region markers; the stable accepted-bore
# path remains unchanged.
X1_R10_CONTEXT_SIZING_ENABLED = True
X1_R10_MARKER_MIN_RADIUS = 0.05
# R13/R18G: when the marker axis is overridden from accepted-bore context, the local
# weak region radius/cross-distance usually describes side contour geometry, not
# the true cylinder radius. Prefer the accepted coaxial bore core radius.
X1_R11_RADIUS_USE_CONTEXT_PRIMITIVE = False
X1_R11_CONTEXT_PRIMITIVE_RADIUS_FACTOR = 1.00

# R13/R18G: estimate the diagnostic pocket radius from the actual weak-wire points,
# reprojected into the plane perpendicular to the context bore axis. This avoids
# both bad extremes seen in R10B/R11: the side-loop radius was too large, while
# the accepted core radius was too small. The selected radius is the densest
# measured radial band above the core radius.
X1_R20B_RADIUS_USE_PROJECTED_POINT_BAND = True
X1_R20B_PROJECTED_RADIUS_MIN_POINTS = 8
X1_R20B_PROJECTED_RADIUS_MIN_BAND_POINTS = 5
X1_R20B_PROJECTED_RADIUS_MIN_BIN_WIDTH = 0.12
X1_R20B_PROJECTED_RADIUS_BIN_FACTOR = 0.055
X1_R20B_PROJECTED_RADIUS_CORE_MIN_FACTOR = 1.08
X1_R20B_PROJECTED_RADIUS_REGION_MAX_FACTOR = 1.18
X1_R20B_PROJECTED_RADIUS_CONTEXT_MAX_FACTOR = 1.10
X1_R20B_FALLBACK_CORE_REGION_GEOMEAN = False

# R20B anchoring: a diagnostic pocket marker is emitted only when the corrected
# context-axis radius is supported by a dense projected point band. This prevents
# falling back to the too-large side-loop radius or the too-small core radius.
X1_R20B_REQUIRE_PROJECTED_RADIUS_ANCHOR = True
X1_R20B_RADIUS_ANCHOR_MIN_BAND_POINTS = 24
X1_R20B_RADIUS_ANCHOR_MIN_USABLE_POINTS = 24
X1_R20B_RADIUS_ANCHOR_MAX_REL_SPREAD = 0.030
X1_R20B_RADIUS_ANCHOR_MIN_CORE_RATIO = 1.15
X1_R20B_RADIUS_ANCHOR_MAX_REGION_RATIO = 1.15
X1_R10_RADIUS_USE_CONTEXT_CROSS = False
X1_R10_CONTEXT_CROSS_RADIUS_FACTOR = 0.92
X1_R10_CONTEXT_HEIGHT_AXIAL_EXTRA_FACTOR = 2.0
X1_R10_CONTEXT_HEIGHT_MAX_ABS = 24.0
X1_R10_CONTEXT_HEIGHT_MAX_AXIS_SPAN_FRACTION = 0.45
X1_R10_CONTEXT_RADIUS_MAX_CROSS_SECTION_FRACTION = 0.18

# R20B non-round feature diagnostics.
# These diagnostics do not emit geometry and do not change the stable R13 bore /
# anchored-pocket path.  They only inspect closed wires that were not accepted as
# round bores and report possible feature forms for later promotion.
X1_PRINT_NONROUND_FORM_DIAGNOSTICS = True
X1_MAX_NONROUND_FORM_LINES = 24
X1_FORM_MIN_POINTS = 5
X1_FORM_MIN_SIZE = 0.25
X1_FORM_MAX_SIZE_FRACTION = 0.55
X1_FORM_HEX_MIN_SCORE = 2.40
X1_FORM_SLOT_MIN_SCORE = 2.20
X1_FORM_ELLIPSE_MIN_SCORE = 2.20
X1_FORM_CORNER_ANGLE_DEG = 28.0
X1_FORM_HEX_CORNER_MIN = 5
X1_FORM_HEX_CORNER_MAX = 7
X1_FORM_HEX_ASPECT_MIN = 0.72
X1_FORM_HEX_ASPECT_MAX = 1.38
X1_FORM_SLOT_ASPECT_MIN = 1.65
X1_FORM_ELLIPSE_ASPECT_MIN = 1.25
X1_FORM_ELLIPSE_ASPECT_MAX = 4.50
X1_FORM_CIRCLE_REL_RMS_REJECT = 0.035

# R20B non-round visual markers. Diagnostic-only; stable bores and anchored
# circular pockets are unchanged. Markers are translucent prisms generated from
# the original detected inner wire, so they show the actual form footprint rather
# than reducing a hex/slot to a cylinder.
X1_EMIT_NONROUND_FORM_MARKERS = True
X1_MAX_NONROUND_FORM_MARKERS = 12
X1_NONROUND_FORM_MARKER_TRANSPARENCY = 72
X1_NONROUND_FORM_MARKER_MIN_SCORE = 2.40
X1_NONROUND_FORM_MARKER_INNER_ONLY = True
X1_NONROUND_FORM_MARKER_HEIGHT_FACTOR = 0.18
X1_NONROUND_FORM_MARKER_MIN_HEIGHT = 1.25
X1_NONROUND_FORM_MARKER_MAX_HEIGHT = 5.00


# R20B chamfer/fase diagnostics for non-round forms.
# These diagnostics do not alter R13/R18G bore or pocket geometry.  They inspect
# nearby coaxial accepted primitives and wire observations to see whether a
# detected form footprint is likely a chamfered mouth rather than the true core
# size/depth of the feature.
X1_PRINT_CHAMFER_FORM_DIAGNOSTICS = True
X1_MAX_CHAMFER_FORM_LINES = 16
X1_CHAMFER_FORM_TYPES = ("HEX_NUT_POCKET_CANDIDATE", "LONG_SLOT_OR_ADJUSTABLE_BORE_CANDIDATE", "ELLIPTIC_OR_OVAL_BORE_CANDIDATE")
X1_CHAMFER_CONTEXT_CENTER_FACTOR = 0.62
X1_CHAMFER_CONTEXT_CENTER_MIN = 2.00
X1_CHAMFER_CONTEXT_AXIS_MAX_DIST = 22.0
X1_CHAMFER_NEAR_RING_CENTER_FACTOR = 0.45
X1_CHAMFER_NEAR_RING_CENTER_MIN = 1.50
X1_CHAMFER_NEAR_RING_AXIAL_MAX = 16.0
X1_CHAMFER_RADIUS_STEP_MIN_RATIO = 0.08
X1_CHAMFER_ANGLE_MIN_DEG = 8.0
X1_CHAMFER_ANGLE_MAX_DEG = 82.0


# R20B chamfer-resolved form markers. Diagnostic-only. The R15/R16 mouth
# markers show the opening footprint, which can be chamfer-inflated. R20B adds
# a second marker that tries to represent the form body/seat by using the first
# smaller same-axis layer after the mouth. This is intentionally separate from
# accepted feature promotion.
X1_EMIT_CHAMFER_RESOLVED_FORM_MARKERS = True
X1_MAX_CHAMFER_RESOLVED_FORM_MARKERS = 12
X1_CHAMFER_RESOLVED_FORM_MARKER_TRANSPARENCY = 62
X1_CHAMFER_RESOLVED_FORM_MIN_SCORE = 2.40
X1_CHAMFER_RESOLVED_FORM_TYPES = ("HEX_NUT_POCKET_CANDIDATE",)
X1_CHAMFER_RESOLVED_MIN_DEPTH = 0.75
X1_CHAMFER_RESOLVED_MAX_DEPTH = 24.0
X1_CHAMFER_RESOLVED_MIN_SCALE = 0.60
X1_CHAMFER_RESOLVED_MAX_SCALE = 1.02
X1_CHAMFER_RESOLVED_LAYER_MIN_DT = 0.50
X1_CHAMFER_RESOLVED_LAYER_MAX_DT = 16.0

X1_CHAMFER_RESOLVED_CORE_CLEARANCE = 1.08

# R20B tessellated axis-side probe.
# This is diagnostic-only and exists for hard imported/tessellated meshes where
# FreeCAD does not expose reliable inner wires or clean CAD-like face loops.
# It scans each object from +/-X, +/-Y, +/-Z, collects side-wall contact points
# near the outside faces, clusters projected outlines, and pairs opposite-side
# openings into bore-like evidence.  It must not promote, resize, or delete any
# accepted R18B/R18A feature.
X1_R20B_ENABLE_TESSELLATED_AXIS_SIDE_PROBE = True
X1_R20B_PROBE_FACE_SAMPLE_CAP = 7000
X1_R20B_PROBE_MAX_SIDE_POINTS = 9000
X1_R20B_PROBE_MIN_SIDE_POINTS = 10
X1_R20B_PROBE_SIDE_BAND_MIN = 0.20
X1_R20B_PROBE_SIDE_BAND_BBOX_FACTOR = 0.010
X1_R20B_SIDE_FACE_NORMAL_MAX_DOT = 0.92
X1_R20B_CLUSTER_GRID_DIVISIONS = 95
X1_R20B_CLUSTER_MIN_POINTS = 8
X1_R20B_CLUSTER_MIN_RADIUS = 0.20
X1_R20B_CLUSTER_MAX_RADIUS_FRACTION = 0.34
X1_R20B_CLUSTER_MAX_REL_RMS = 0.22
X1_R20B_CLUSTER_MAX_ASPECT = 5.50
X1_R20B_PAIR_CENTER_FACTOR = 0.80
X1_R20B_PAIR_CENTER_MIN = 2.25
X1_R20B_PAIR_RADIUS_RATIO_MAX = 2.35
X1_R20B_MAX_SIDE_CANDIDATES_PER_SIDE = 12
X1_R20B_MAX_PAIR_MARKERS = 0  # R20B: collect side-pair evidence but do not draw raw side-scan markers by default
X1_R20B_MAX_SINGLE_MARKERS = 0  # R20B: collect single-side evidence but do not draw raw side-scan markers by default
X1_R20B_MARKER_TRANSPARENCY = 74
X1_R20B_SINGLE_MARKER_HEIGHT_FACTOR = 0.18
X1_R20B_SINGLE_MARKER_MIN_HEIGHT = 0.75
X1_R20B_SINGLE_MARKER_MAX_HEIGHT = 4.0
X1_R20B_ACCEPTED_CENTER_FACTOR = 0.55
X1_R20B_ACCEPTED_CENTER_MIN = 1.75
X1_R20B_ACCEPTED_RADIUS_FACTOR = 1.35

# R20B consolidated tessellated ledger.
# Diagnostic-only: this does not promote any candidate into the accepted bore path.
# It merges duplicate R18J/R20B side-scan hits and FAST layer-stack evidence into
# object-local candidate families so we can compare the three test objects safely.
X1_R20B_ENABLE_CONSOLIDATED_TESSELLATED_LEDGER = True
X1_R20B_CONSOLIDATED_LEDGER_MARKERS = False  # R20B: structured ledger first; visual consolidated markers are opt-in
X1_R20B_CONSOLIDATED_MARKER_TRANSPARENCY = 55
X1_R20B_CONSOLIDATED_MAX_MARKERS = 36
X1_R20B_CONSOLIDATE_CENTER_MIN = 1.60
X1_R20B_CONSOLIDATE_CENTER_RADIUS_FACTOR = 0.62
X1_R20B_CONSOLIDATE_RADIUS_RATIO_MAX = 1.72
X1_R20B_SINGLE_WEAK_MIN_SCORE = 4.20
X1_R20B_SINGLE_NEAR_ACCEPTED_CENTER_FACTOR = 0.90
X1_R20B_SINGLE_NEAR_ACCEPTED_RADIUS_FACTOR = 1.85
X1_R20B_SINGLE_SUPPRESS_NEAR_ACCEPTED = True
X1_R20B_PAIR_MIN_EVIDENCE_SCORE = 4.00
X1_R20B_FAST_STACK_WEIGHT = 3.50
X1_R20B_SIDE_PAIR_WEIGHT = 4.50
X1_R20B_SIDE_SINGLE_WEIGHT = 1.25
X1_R20B_ACCEPTED_WEIGHT = 6.00
X1_R20B_ONE_RING_CONTEXT_WEIGHT = 0.50

# R20B guard: FAST-only tessellation_only_unanchored entries are evidence-ledger
# context only. They remain printed for analysis, but no consolidated visual
# marker is emitted unless another independent system also supports them. This
# specifically removes the observed false-positive X/r≈9.102 diagnostic marker
# while preserving the accepted R18A/R18B path and the useful R18J side-pair
# candidates on Mesh025.
X1_R20B_SUPPRESS_FAST_ONLY_TESSELLATION_ONLY_UNANCHORED = True
X1_R20B_UNANCHORED_FAST_ONLY_MAX_EVIDENCE = 6.00

# R20B structured export / conservative promotion guard.
# Diagnostic-only: exports a machine-readable evidence ledger for FAR Mesh
# integration and suppresses raw side-pair-only evidence from visual promotion.
X1_R20B_EXPORT_STRUCTURED_LEDGER = True
X1_R20B_EXPORT_CSV_LEDGER = True
X1_R20B_EXPORT_JSON_LEDGER = True
X1_R20B_EXPORT_BASENAME = "x1_2026_r20b_feature_evidence_ledger"
X1_R20B_SUPPRESS_SIDE_PAIR_ONLY_MARKERS = True
X1_R20B_SIDE_PAIR_CONTEXT_MAX_DEPTH_RADIUS_RATIO = 24.0
X1_R20B_LEDGER_SCHEMA_VERSION = "r20b.1"

# R20B tessellated review markers.
# Diagnostic-only: Tier A keeps the R19B strong side-pair/body candidates visible,
# while Tier B adds separated context markers for strong paired tessellated
# evidence that R19B correctly kept suppressed. Accepted primitives and emitted
# cylinders remain unchanged. These markers are deliberately separated from the
# consolidated-ledger visual marker switch and carry NOT_ACCEPTED metadata.
X1_R20B_EMIT_TESSELLATED_REVIEW_MARKERS = True
X1_R20B_REVIEW_MARKER_REQUIRED_SOURCE_KIND = "side_pair"
X1_R20B_REVIEW_TIER_A_CLASSES = ("tessellated_chamfer_body_candidate",)
X1_R20B_REVIEW_TIER_A_MIN_EVIDENCE = 15.0
X1_R20B_REVIEW_TIER_B_CLASSES = ("side_pair_context_only", "side_pair_context_high_depth_ratio", "tessellated_bore_candidate")
X1_R20B_REVIEW_TIER_B_MIN_EVIDENCE = 20.0
X1_R20B_REVIEW_MARKER_MAX_MARKERS = 24
X1_R20B_REVIEW_MARKER_TIER_A_TRANSPARENCY = 46
X1_R20B_REVIEW_MARKER_TIER_B_TRANSPARENCY = 68
X1_R20B_REVIEW_TIER_A_LABEL = "TIER_A_STRONG | DIAGNOSTIC_ONLY | NOT_ACCEPTED_FEATURE | TESSELLATED_SIDE_PAIR_BODY_EVIDENCE"
X1_R20B_REVIEW_TIER_B_LABEL = "TIER_B_CONTEXT | DIAGNOSTIC_ONLY | NOT_ACCEPTED_FEATURE | SUPPRESSED_TESSELLATED_CONTEXT"
# Backward-compatible aliases for older helper code.
X1_R20B_REVIEW_MARKER_CLASSES = X1_R20B_REVIEW_TIER_A_CLASSES
X1_R20B_REVIEW_MARKER_MIN_EVIDENCE = X1_R20B_REVIEW_TIER_A_MIN_EVIDENCE
X1_R20B_REVIEW_MARKER_TRANSPARENCY = X1_R20B_REVIEW_MARKER_TIER_A_TRANSPARENCY
X1_R20B_REVIEW_MARKER_LABEL = X1_R20B_REVIEW_TIER_A_LABEL

# R20B guarded promotion-preview cylinders.
# Diagnostic-only: these are not accepted primitives and do not change the
# stable emitted-cylinder count.  They are visual restoration candidates for
# strong Tier A tessellated side-pair evidence, especially Mesh025-like imports.
X1_R20B_EMIT_PROMOTION_PREVIEW_CYLINDERS = True
X1_R20B_PROMOTION_PREVIEW_CLASSES = ("tessellated_chamfer_body_candidate", "missing_bore_with_chamfer_candidate")
X1_R20B_PROMOTION_PREVIEW_MIN_DEPTH_RADIUS_RATIO = 2.0
X1_R20B_PROMOTION_PREVIEW_MAX_MARKERS = 24
X1_R20B_PROMOTION_PREVIEW_TRANSPARENCY = 34
X1_R20B_PROMOTION_PREVIEW_COLOR = (0.0, 0.85, 0.85)
X1_R20B_PROMOTION_PREVIEW_LABEL = "R20B_PROMOTION_PREVIEW | DIAGNOSTIC_ONLY | NOT_ACCEPTED_FEATURE | GUARDED_TIER_A_TESSELLATED_EVIDENCE"

# R20B guarded accepted promotion.
# This is the first narrowly-scoped restoration step: only entries already
# classified as missing_bore_with_chamfer_candidate and independently confirmed
# by BOTH FAST stack evidence and tessellated side-pair evidence are emitted as
# accepted path cylinders. Side-pair-only Tier A/B candidates remain diagnostic.
X1_R20B_ENABLE_GUARDED_MISSING_BORE_PROMOTION = True
X1_R20B_ACCEPTED_PROMOTION_CLASSES = ("missing_bore_with_chamfer_candidate",)
X1_R20B_ACCEPTED_PROMOTION_REQUIRED_SOURCE_KINDS = ("fast_stack", "side_pair")
X1_R20B_ACCEPTED_PROMOTION_MIN_EVIDENCE = 20.0
X1_R20B_ACCEPTED_PROMOTION_MIN_DEPTH_RADIUS_RATIO = 2.0
X1_R20B_ACCEPTED_PROMOTION_MAX_RADIUS_RATIO = 1.80
X1_R20B_ACCEPTED_PROMOTION_MAX_MARKERS = 16
X1_R20B_ACCEPTED_PROMOTION_LABEL = "R20B_ACCEPTED_PATH_PROMOTION | GUARDED_FAST_STACK_PLUS_SIDE_PAIR | MISSING_BORE_WITH_CHAMFER"

# Runtime collection for the JSON/CSV export. Reset in main().
X1_R20B_STRUCTURED_LEDGER_ROWS = []


# =============================================================================
# Console helpers
# =============================================================================


def x1_msg(text):
    if App is not None:
        try:
            App.Console.PrintMessage(str(text) + "\n")
            return
        except Exception:
            pass
    print(text)


def x1_warn(text):
    if App is not None:
        try:
            App.Console.PrintWarning(str(text) + "\n")
            return
        except Exception:
            pass
    print("WARNING: " + str(text))


def x1_err(text):
    if App is not None:
        try:
            App.Console.PrintError(str(text) + "\n")
            return
        except Exception:
            pass
    print("ERROR: " + str(text))


# =============================================================================
# Vector helpers
# =============================================================================


def v_new(x, y, z):
    return App.Vector(float(x), float(y), float(z))


def v_dot(a, b):
    return float(a.x * b.x + a.y * b.y + a.z * b.z)


def v_len(a):
    return math.sqrt(max(0.0, v_dot(a, a)))


def v_unit(a):
    length = v_len(a)
    if length <= 1.0e-12:
        return v_new(0.0, 0.0, 1.0)
    return v_new(a.x / length, a.y / length, a.z / length)


def v_scale(a, s):
    return v_new(a.x * s, a.y * s, a.z * s)


def v_add(a, b):
    return v_new(a.x + b.x, a.y + b.y, a.z + b.z)


def v_sub(a, b):
    return v_new(a.x - b.x, a.y - b.y, a.z - b.z)


def v_dist(a, b):
    return v_len(v_sub(a, b))


def axis_vector(axis_name):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return v_new(1, 0, 0)
    if axis_name == "Y":
        return v_new(0, 1, 0)
    return v_new(0, 0, 1)


def axis_hint(axis):
    a = v_unit(axis)
    dots = [abs(a.x), abs(a.y), abs(a.z)]
    best = max(dots)
    if best < 0.90:
        return "FREE"
    idx = dots.index(best)
    return ("X", "Y", "Z")[idx]


def canonical_axis(axis):
    a = v_unit(axis)
    values = [abs(a.x), abs(a.y), abs(a.z)]
    major = values.index(max(values))
    sign_value = [a.x, a.y, a.z][major]
    if sign_value < 0.0:
        a = v_scale(a, -1.0)
    return a


def axis_value(point, axis):
    return v_dot(point, canonical_axis(axis))


def line_base_from_points(points, axis):
    """Return the mean line base perpendicular to axis."""
    axis = canonical_axis(axis)
    if not points:
        return v_new(0, 0, 0)
    accum = v_new(0, 0, 0)
    for p in points:
        perp = v_sub(p, v_scale(axis, v_dot(p, axis)))
        accum = v_add(accum, perp)
    return v_scale(accum, 1.0 / float(len(points)))


def line_distance_parallel(p1, axis1, p2, axis2):
    a1 = canonical_axis(axis1)
    a2 = canonical_axis(axis2)
    if abs(v_dot(a1, a2)) < X1_AXIS_PARALLEL_DOT:
        return 999999.0
    d = v_sub(p2, p1)
    return v_len(v_sub(d, v_scale(a1, v_dot(d, a1))))


def median(values):
    vals = sorted(float(v) for v in values)
    if not vals:
        return 0.0
    n = len(vals)
    mid = n // 2
    if n % 2:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def bbox_dimensions(bb):
    try:
        return (float(bb.XLength), float(bb.YLength), float(bb.ZLength))
    except Exception:
        return (0.0, 0.0, 0.0)


def bbox_diag(bb):
    dx, dy, dz = bbox_dimensions(bb)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def cross_section_span_for_axis(bb, axis_hint_value):
    dx, dy, dz = bbox_dimensions(bb)
    if axis_hint_value == "X":
        return min(abs(dy), abs(dz))
    if axis_hint_value == "Y":
        return min(abs(dx), abs(dz))
    if axis_hint_value == "Z":
        return min(abs(dx), abs(dy))
    return min(abs(dx), abs(dy), abs(dz))


def point_inside_bbox(point, bb, margin):
    try:
        return (
            point.x >= bb.XMin - margin and point.x <= bb.XMax + margin and
            point.y >= bb.YMin - margin and point.y <= bb.YMax + margin and
            point.z >= bb.ZMin - margin and point.z <= bb.ZMax + margin
        )
    except Exception:
        return True


def vec_to_text(v):
    try:
        return "(%.3f, %.3f, %.3f)" % (float(v.x), float(v.y), float(v.z))
    except Exception:
        return str(v)


# =============================================================================
# 2D circle fitting without numpy
# =============================================================================


def solve_3x3(a, b):
    """Small Gaussian solver for 3x3 linear systems."""
    m = [
        [float(a[0][0]), float(a[0][1]), float(a[0][2]), float(b[0])],
        [float(a[1][0]), float(a[1][1]), float(a[1][2]), float(b[1])],
        [float(a[2][0]), float(a[2][1]), float(a[2][2]), float(b[2])],
    ]
    for col in range(3):
        pivot = col
        for row in range(col + 1, 3):
            if abs(m[row][col]) > abs(m[pivot][col]):
                pivot = row
        if abs(m[pivot][col]) <= 1.0e-12:
            return None
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        for k in range(col, 4):
            m[col][k] /= div
        for row in range(3):
            if row == col:
                continue
            factor = m[row][col]
            for k in range(col, 4):
                m[row][k] -= factor * m[col][k]
    return (m[0][3], m[1][3], m[2][3])


def fit_circle_2d(points2d):
    """
    Kasa-style least-squares circle fit.

    Returns (cx, cy, radius, rel_rms).  The fit is intentionally simple and
    deterministic for FreeCAD macro use.  The caller performs strict RMS checks.
    """
    pts = [(float(x), float(y)) for x, y in points2d]
    if len(pts) < X1_MIN_RING_POINTS:
        return None

    sx = sy = sx2 = sy2 = sxy = 0.0
    sxz = syz = sz = 0.0
    n = float(len(pts))
    for x, y in pts:
        z = x * x + y * y
        sx += x
        sy += y
        sx2 += x * x
        sy2 += y * y
        sxy += x * y
        sxz += x * z
        syz += y * z
        sz += z

    # x^2+y^2 + D*x + E*y + F = 0
    mat = [[sx2, sxy, sx], [sxy, sy2, sy], [sx, sy, n]]
    rhs = [-sxz, -syz, -sz]
    sol = solve_3x3(mat, rhs)
    if sol is None:
        return None
    d, e, f = sol
    cx = -0.5 * d
    cy = -0.5 * e
    r2 = cx * cx + cy * cy - f
    if r2 <= 1.0e-12:
        return None
    radius = math.sqrt(r2)
    if radius < X1_MIN_RADIUS:
        return None

    residuals = []
    for x, y in pts:
        rr = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        residuals.append(rr - radius)
    rms = math.sqrt(sum(r * r for r in residuals) / max(1.0, float(len(residuals))))
    rel_rms = rms / max(radius, 1.0e-9)
    return (cx, cy, radius, rel_rms)


# =============================================================================
# Wire and edge helpers
# =============================================================================


def edge_points(edge, count=12):
    pts = []
    try:
        # FreeCAD supports discretize(Number=n) for most curve types.
        raw = edge.discretize(Number=int(count))
        for p in raw:
            pts.append(App.Vector(p.x, p.y, p.z))
        if pts:
            return pts
    except Exception:
        pass
    try:
        for v in edge.Vertexes:
            pts.append(App.Vector(v.Point.x, v.Point.y, v.Point.z))
    except Exception:
        pass
    return pts


def wire_points(wire, samples_per_edge=8):
    pts = []
    try:
        for edge in wire.Edges:
            pts.extend(edge_points(edge, samples_per_edge))
    except Exception:
        pass
    return unique_points(pts)


def unique_points(points, tol=1.0e-6):
    seen = set()
    out = []
    scale = 1.0 / max(tol, 1.0e-12)
    for p in points:
        key = (int(round(p.x * scale)), int(round(p.y * scale)), int(round(p.z * scale)))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def wire_is_closed(wire):
    try:
        return bool(wire.isClosed())
    except Exception:
        pass
    try:
        pts = wire_points(wire, 2)
        if len(pts) >= 2:
            return v_dist(pts[0], pts[-1]) <= 1.0e-5
    except Exception:
        pass
    return False


def wire_length(wire):
    try:
        return float(wire.Length)
    except Exception:
        total = 0.0
        try:
            for e in wire.Edges:
                total += float(e.Length)
        except Exception:
            pass
        return total


def wire_same(w1, w2):
    try:
        return bool(w1.isSame(w2))
    except Exception:
        return False


def plane_axis_from_points(points, bb_diag_value):
    """
    Infer an X/Y/Z plane axis from point extents.

    For a circular bore opening on an axis-aligned CAD model, one coordinate has
    tiny extent.  That coordinate is the bore axis.
    """
    if len(points) < X1_MIN_RING_POINTS:
        return None
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    spans = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
    min_span = min(spans)
    max_span = max(spans)
    if max_span <= 1.0e-12:
        return None
    plane_tol = max(X1_PLANE_ABS_TOL, bb_diag_value * 1.0e-5, max_span * X1_MAX_RING_PLANE_REL)
    if min_span > plane_tol:
        return None
    idx = spans.index(min_span)
    return ("X", "Y", "Z")[idx]


def points_to_2d(points, axis_name):
    if axis_name == "X":
        return [(p.y, p.z) for p in points]
    if axis_name == "Y":
        return [(p.x, p.z) for p in points]
    return [(p.x, p.y) for p in points]


def center_from_axis_and_2d(axis_name, axial, cx, cy):
    if axis_name == "X":
        return v_new(axial, cx, cy)
    if axis_name == "Y":
        return v_new(cx, axial, cy)
    return v_new(cx, cy, axial)


# =============================================================================
# Observation model
# =============================================================================


def new_ring_observation(axis, center, radius, source, strength, rel_rms=0.0, point_count=0, inner=False, analytic=False, points=None):
    axis = canonical_axis(axis)
    t = v_dot(center, axis)
    # Keep the sampled wire points for diagnostic-only pocket radius estimation.
    # The accepted bore path does not depend on these points, so storing them is
    # safe and makes later marker sizing use real geometry instead of only a
    # fitted side-loop radius.
    return {
        "kind": "ring",
        "axis": axis,
        "axis_hint": axis_hint(axis),
        "center": center,
        "radius": float(radius),
        "t_min": t,
        "t_max": t,
        "source": source,
        "strength": float(strength),
        "rel_rms": float(rel_rms),
        "point_count": int(point_count),
        "is_inner_wire": bool(inner),
        "is_analytic": bool(analytic),
        "points": list(points or []),
    }


def new_cylinder_observation(axis, base, radius, t_min, t_max, source, strength=1.0):
    axis = canonical_axis(axis)
    return {
        "kind": "cylinder_face",
        "axis": axis,
        "axis_hint": axis_hint(axis),
        "center": base,
        "radius": float(radius),
        "t_min": float(t_min),
        "t_max": float(t_max),
        "source": source,
        "strength": float(strength),
        "rel_rms": 0.0,
        "point_count": 0,
        "is_inner_wire": False,
        "is_analytic": True,
    }


# =============================================================================
# Observation collection
# =============================================================================


def collect_analytic_cylinders(shape, label, log):
    obs = []
    try:
        faces = list(shape.Faces)
    except Exception:
        return obs

    for i, face in enumerate(faces, start=1):
        try:
            surf = face.Surface
            if not isinstance(surf, Part.Cylinder):
                continue
            axis = canonical_axis(App.Vector(surf.Axis.x, surf.Axis.y, surf.Axis.z))
            radius = float(surf.Radius)
            if radius < X1_MIN_RADIUS:
                continue
            pts = []
            try:
                for edge in face.Edges:
                    pts.extend(edge_points(edge, 8))
            except Exception:
                pass
            if len(pts) < 2:
                continue
            base = line_base_from_points(pts, axis)
            t_vals = [v_dot(p, axis) for p in pts]
            t_min = min(t_vals)
            t_max = max(t_vals)
            if t_max - t_min < X1_MIN_DEPTH:
                continue
            obs.append(new_cylinder_observation(axis, base, radius, t_min, t_max, "%s:analytic_cylinder_face_%d" % (label, i), 1.0))
        except Exception as exc:
            log.append(("warning", "analytic cylinder face failed: %s" % exc))
    return obs


def collect_analytic_circle_edges(shape, label, log):
    obs = []
    try:
        edges = list(shape.Edges)
    except Exception:
        return obs

    for i, edge in enumerate(edges, start=1):
        try:
            if not isinstance(edge.Curve, Part.Circle):
                continue
            curve = edge.Curve
            radius = float(curve.Radius)
            if radius < X1_MIN_RADIUS:
                continue
            axis = App.Vector(curve.Axis.x, curve.Axis.y, curve.Axis.z)
            center = App.Vector(curve.Center.x, curve.Center.y, curve.Center.z)
            # Full circles are strong, arcs are useful but weaker.
            coverage = 1.0
            try:
                coverage = clamp(float(edge.Length) / max(2.0 * math.pi * radius, 1.0e-9), 0.0, 1.0)
            except Exception:
                coverage = 1.0
            if coverage < 0.20:
                continue
            strength = 0.65 + 0.30 * coverage
            try:
                pts = edge_points(edge, 16)
            except Exception:
                pts = []
            obs.append(new_ring_observation(axis, center, radius, "%s:analytic_circle_edge_%d" % (label, i), strength, 0.0, len(pts), False, True, pts))
        except Exception as exc:
            log.append(("warning", "analytic circle edge failed: %s" % exc))
    return obs


def ring_from_wire_points(points, axis_name, source, strength, inner, analytic, bb_diag_value):
    if len(points) < X1_MIN_RING_POINTS:
        return None
    axis_name = str(axis_name).upper()
    axis = axis_vector(axis_name)
    axial = median([v_dot(p, axis) for p in points])
    pts2 = points_to_2d(points, axis_name)
    fit = fit_circle_2d(pts2)
    if fit is None:
        return None
    cx, cy, radius, rel_rms = fit
    if rel_rms > X1_MAX_RING_REL_RMS:
        return None
    center = center_from_axis_and_2d(axis_name, axial, cx, cy)
    return new_ring_observation(axis, center, radius, source, strength, rel_rms, len(points), inner, analytic, points)


def collect_face_inner_wires(shape, label, log):
    """
    Collect true inner face wires.

    These are much stronger than arbitrary global wires because FreeCAD already
    tells us the wire is a hole loop inside a face boundary.
    """
    obs = []
    try:
        faces = list(shape.Faces)
        bb_diag_value = bbox_diag(shape.BoundBox)
    except Exception:
        return obs

    for fi, face in enumerate(faces, start=1):
        try:
            wires = list(face.Wires)
            if len(wires) < 2:
                continue
            outer = None
            try:
                outer = face.OuterWire
            except Exception:
                pass

            # If OuterWire identity is unreliable, also treat the longest wire as
            # the outer boundary and ignore it.
            lengths = [(wire_length(w), idx, w) for idx, w in enumerate(wires)]
            longest_idx = max(lengths, key=lambda x: x[0])[1] if lengths else -1

            for wi, wire in enumerate(wires, start=1):
                if outer is not None and wire_same(wire, outer):
                    continue
                if outer is None and (wi - 1) == longest_idx:
                    continue
                if not wire_is_closed(wire):
                    continue
                pts = wire_points(wire, 10)
                axis_name = plane_axis_from_points(pts, bb_diag_value)
                if axis_name is None:
                    # Fall back to face normal if the points are slightly noisy.
                    try:
                        u0, u1, v0, v1 = face.ParameterRange
                        n = face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1))
                        axis_name = axis_hint(n)
                        if axis_name == "FREE":
                            continue
                    except Exception:
                        continue
                ring = ring_from_wire_points(pts, axis_name, "%s:face_%d_inner_wire_%d" % (label, fi, wi), 1.00, True, False, bb_diag_value)
                if ring is not None:
                    obs.append(ring)
        except Exception as exc:
            log.append(("warning", "face inner wire failed: %s" % exc))
    return obs


def collect_global_closed_wires(shape, label, log):
    """
    Collect closed circular wires from the whole shape.

    This is weaker than inner face wires.  It is mainly for tessellated/imported
    solids where bores are represented as polygonal circular loops rather than
    Part.Circle edges.
    """
    obs = []
    try:
        wires = list(shape.Wires)
        bb_diag_value = bbox_diag(shape.BoundBox)
    except Exception:
        return obs

    for wi, wire in enumerate(wires, start=1):
        try:
            if not wire_is_closed(wire):
                continue
            pts = wire_points(wire, 8)
            axis_name = plane_axis_from_points(pts, bb_diag_value)
            if axis_name is None:
                continue
            ring = ring_from_wire_points(pts, axis_name, "%s:global_closed_wire_%d" % (label, wi), 0.58, False, False, bb_diag_value)
            if ring is not None:
                obs.append(ring)
        except Exception as exc:
            log.append(("warning", "global wire failed: %s" % exc))
    return obs


def dedupe_observations(observations):
    """Remove near-identical rings produced through multiple routes."""
    out = []
    for obs in observations:
        duplicate_index = None
        for i, old in enumerate(out):
            if obs["kind"] != old["kind"]:
                continue
            if abs(v_dot(obs["axis"], old["axis"])) < X1_AXIS_PARALLEL_DOT:
                continue
            if abs(obs["radius"] - old["radius"]) > max(0.05, obs["radius"] * 0.03, old["radius"] * 0.03):
                continue
            if line_distance_parallel(obs["center"], obs["axis"], old["center"], old["axis"]) > max(0.05, obs["radius"] * 0.03):
                continue
            if abs(v_dot(obs["center"], obs["axis"]) - v_dot(old["center"], old["axis"])) > max(0.05, obs["radius"] * 0.03):
                continue
            duplicate_index = i
            break
        if duplicate_index is None:
            out.append(obs)
        else:
            # Preserve the stronger observation/source.
            if obs.get("strength", 0.0) > out[duplicate_index].get("strength", 0.0):
                out[duplicate_index] = obs
    return out


def collect_observations(shape, label, log):
    observations = []
    observations.extend(collect_analytic_cylinders(shape, label, log))
    observations.extend(collect_analytic_circle_edges(shape, label, log))
    observations.extend(collect_face_inner_wires(shape, label, log))
    observations.extend(collect_global_closed_wires(shape, label, log))
    return dedupe_observations(observations)


# =============================================================================
# Hypothesis grouping and primitive construction
# =============================================================================


def obs_compatible(group, obs):
    axis = group["axis"]
    if abs(v_dot(axis, obs["axis"])) < X1_AXIS_PARALLEL_DOT:
        return False
    group_radius = median([o["radius"] for o in group["observations"]])
    radius_tol = max(0.08, group_radius * X1_RING_RADIUS_REL_TOL, obs["radius"] * X1_RING_RADIUS_REL_TOL)
    if abs(obs["radius"] - group_radius) > radius_tol:
        return False
    group_base = line_base_from_points([o["center"] for o in group["observations"]], axis)
    center_tol = max(X1_CENTER_ABS_TOL, max(group_radius, obs["radius"]) * X1_CENTER_RADIUS_FACTOR)
    if line_distance_parallel(group_base, axis, obs["center"], obs["axis"]) > center_tol:
        return False
    return True


def build_groups(observations):
    groups = []
    # Put strong evidence first so weaker duplicate wires attach to the right group.
    ordered = sorted(observations, key=lambda o: -float(o.get("strength", 0.0)))
    for obs in ordered:
        placed = False
        for group in groups:
            if obs_compatible(group, obs):
                group["observations"].append(obs)
                placed = True
                break
        if not placed:
            groups.append({"axis": obs["axis"], "observations": [obs]})
    return groups


def group_support_stats(group):
    obs = group["observations"]
    rings = [o for o in obs if o["kind"] == "ring"]
    cyls = [o for o in obs if o["kind"] == "cylinder_face"]
    inner_count = sum(1 for o in rings if o.get("is_inner_wire"))
    analytic_ring_count = sum(1 for o in rings if o.get("is_analytic"))
    unknown_ring_count = len(rings) - inner_count - analytic_ring_count
    return rings, cyls, inner_count, analytic_ring_count, unknown_ring_count


def reject_large_unknown_outer(group, bb):
    """Reject obvious outer silhouette rings if no strong ring/cylinder exists."""
    rings, cyls, inner_count, analytic_ring_count, unknown_count = group_support_stats(group)
    if cyls or inner_count or analytic_ring_count:
        return False
    if not rings or bb is None:
        return False
    axis_name = axis_hint(group["axis"])
    span = cross_section_span_for_axis(bb, axis_name)
    if span <= 1.0e-9:
        return False
    radius = median([r["radius"] for r in rings])
    return radius > X1_UNKNOWN_RING_MAX_CROSS_SECTION_FRACTION * span


def primitive_from_group(group, bb):
    obs = group["observations"]
    axis = canonical_axis(group["axis"])
    rings, cyls, inner_count, analytic_ring_count, unknown_count = group_support_stats(group)
    radius = median([o["radius"] for o in obs])

    if radius < X1_MIN_RADIUS:
        return None, "radius too small"
    if reject_large_unknown_outer(group, bb):
        return None, "large unknown outer/silhouette ring rejected"

    # Need actual axial extent.  A single ring without cylinder-face evidence is
    # only an opening loop and cannot define bore depth.
    if not cyls and len(rings) < X1_MIN_RINGS_WITHOUT_CYL_FACE:
        return None, "only one ring and no cylinder-face depth evidence"
    if not cyls and (inner_count + analytic_ring_count) < X1_MIN_INNER_OR_ANALYTIC_RINGS_FOR_WEAK_STACK:
        # Two global outer-looking wires are still weak; require at least one
        # inner face wire or analytic circle unless the group is very clean and
        # not large.  This prevents the earlier random big cylinders.
        if unknown_count >= len(rings):
            return None, "ring stack has only weak global closed-wire evidence"

    t_values = []
    for o in obs:
        if o.get("t_min") is not None:
            t_values.append(float(o["t_min"]))
        if o.get("t_max") is not None:
            t_values.append(float(o["t_max"]))
        t_values.append(v_dot(o["center"], axis))
    if not t_values:
        return None, "no axial support"
    t_min = min(t_values)
    t_max = max(t_values)
    depth = t_max - t_min
    if depth < X1_MIN_DEPTH:
        return None, "depth too small"

    # Stable centerline from all observation centers.
    base = line_base_from_points([o["center"] for o in obs], axis)
    start = v_add(base, v_scale(axis, t_min - X1_CYLINDER_OVERLAP))
    end = v_add(base, v_scale(axis, t_max + X1_CYLINDER_OVERLAP))
    height = v_dist(start, end)

    # BBox guard.  Endpoints must remain close to the selected part volume.
    margin = max(radius * 1.2, 0.5)
    if bb is not None:
        if not point_inside_bbox(start, bb, margin) or not point_inside_bbox(end, bb, margin):
            return None, "bbox endpoint guard rejected"

    # Confidence deliberately rewards direct/strong evidence over point-slice fits.
    avg_strength = sum(float(o.get("strength", 0.5)) for o in obs) / max(1.0, float(len(obs)))
    support = 0.18 * len(rings) + 0.30 * len(cyls) + 0.18 * inner_count + 0.12 * analytic_ring_count
    depth_score = clamp(depth / max(radius * 1.5, 1.0e-9), 0.0, 1.0)
    confidence = clamp(0.20 + 0.35 * avg_strength + support + 0.10 * depth_score, 0.0, 1.0)
    if confidence < X1_MIN_CONFIDENCE:
        return None, "confidence below threshold %.3f" % confidence

    if len(cyls) > 0:
        profile = "ANALYTIC_CYLINDER_BORE"
    elif inner_count >= 2:
        profile = "INNER_WIRE_THROUGH_BORE"
    elif inner_count >= 1:
        profile = "INNER_WIRE_BORE_CANDIDATE"
    elif analytic_ring_count >= 2:
        profile = "ANALYTIC_RING_BORE"
    else:
        profile = "WEAK_WIRE_STACK_BORE"

    primitive = {
        "axis": axis,
        "axis_hint": axis_hint(axis),
        "base": base,
        "start": start,
        "end": end,
        "radius": radius,
        "diameter": 2.0 * radius,
        "height": height,
        "depth": depth,
        "confidence": confidence,
        "profile": profile,
        "ring_count": len(rings),
        "cylinder_face_count": len(cyls),
        "inner_ring_count": inner_count,
        "analytic_ring_count": analytic_ring_count,
        "unknown_ring_count": unknown_count,
        "observations": obs,
        "sources": sorted(set(o.get("source", "?") for o in obs)),
    }
    return primitive, None


def build_primitives(observations, bb):
    groups = build_groups(observations)
    primitives = []
    rejected = []
    for group in groups:
        prim, reason = primitive_from_group(group, bb)
        if prim is None:
            rejected.append((group, reason))
        else:
            primitives.append(prim)
    return primitives, rejected


# =============================================================================
# Primitive fusion
# =============================================================================


def primitive_overlap_1d(a, b):
    axis = a["axis"]
    vals_a = [v_dot(a["start"], axis), v_dot(a["end"], axis)]
    vals_b = [v_dot(b["start"], axis), v_dot(b["end"], axis)]
    a0, a1 = min(vals_a), max(vals_a)
    b0, b1 = min(vals_b), max(vals_b)
    return min(a1, b1) - max(a0, b0)


def primitives_same_bore(a, b):
    if abs(v_dot(a["axis"], b["axis"])) < X1_AXIS_PARALLEL_DOT:
        return False
    r_ref = max(a["radius"], b["radius"])
    if abs(a["radius"] - b["radius"]) > max(0.08, r_ref * X1_RING_RADIUS_REL_TOL):
        return False
    if line_distance_parallel(a["base"], a["axis"], b["base"], b["axis"]) > max(X1_CENTER_ABS_TOL, r_ref * X1_CENTER_RADIUS_FACTOR):
        return False
    if primitive_overlap_1d(a, b) < -max(1.0, r_ref * 0.35):
        return False
    return True


def merge_primitives(a, b):
    axis = canonical_axis(a["axis"])
    radius = median([a["radius"], b["radius"]])
    all_obs = list(a.get("observations", [])) + list(b.get("observations", []))
    base = line_base_from_points([o["center"] for o in all_obs], axis)
    t_values = []
    for p in (a["start"], a["end"], b["start"], b["end"]):
        t_values.append(v_dot(p, axis))
    t_min = min(t_values)
    t_max = max(t_values)
    start = v_add(base, v_scale(axis, t_min))
    end = v_add(base, v_scale(axis, t_max))
    merged = dict(a)
    merged["axis"] = axis
    merged["axis_hint"] = axis_hint(axis)
    merged["base"] = base
    merged["start"] = start
    merged["end"] = end
    merged["radius"] = radius
    merged["diameter"] = 2.0 * radius
    merged["height"] = v_dist(start, end)
    merged["depth"] = merged["height"]
    merged["confidence"] = max(a.get("confidence", 0.0), b.get("confidence", 0.0))
    merged["profile"] = "DUPLICATE_MERGED_" + str(a.get("profile", "BORE"))
    merged["ring_count"] = int(a.get("ring_count", 0)) + int(b.get("ring_count", 0))
    merged["cylinder_face_count"] = int(a.get("cylinder_face_count", 0)) + int(b.get("cylinder_face_count", 0))
    merged["inner_ring_count"] = int(a.get("inner_ring_count", 0)) + int(b.get("inner_ring_count", 0))
    merged["analytic_ring_count"] = int(a.get("analytic_ring_count", 0)) + int(b.get("analytic_ring_count", 0))
    merged["unknown_ring_count"] = int(a.get("unknown_ring_count", 0)) + int(b.get("unknown_ring_count", 0))
    merged["observations"] = all_obs
    merged["sources"] = sorted(set(a.get("sources", []) + b.get("sources", [])))
    return merged


def fuse_primitives(primitives):
    todo = list(primitives)
    fused = []
    while todo:
        current = todo.pop(0)
        changed = True
        while changed:
            changed = False
            keep = []
            for other in todo:
                if primitives_same_bore(current, other):
                    current = merge_primitives(current, other)
                    changed = True
                else:
                    keep.append(other)
            todo = keep
        fused.append(current)
    fused.sort(key=lambda p: (-p.get("confidence", 0.0), p.get("axis_hint", ""), -p.get("radius", 0.0)))
    return fused



# =============================================================================
# R5 feature/profile annotation and reporting
# =============================================================================


def primitive_axis_interval(p, axis=None):
    """Return sorted axial interval for a primitive."""
    if axis is None:
        axis = p.get("axis", axis_vector("Z"))
    a = v_dot(p["start"], axis)
    b = v_dot(p["end"], axis)
    return (min(a, b), max(a, b))


def interval_gap(a0, a1, b0, b1):
    """Positive gap between two 1-D intervals, or 0 if they touch/overlap."""
    if a1 < b0:
        return b0 - a1
    if b1 < a0:
        return a0 - b1
    return 0.0


def primitives_coaxial_for_stack(a, b):
    """Conservative relation for multi-radius stepped/counterbore stacks.

    This does not fuse primitives.  It only identifies that two accepted
    primitives likely belong to the same physical bore/pocket stack.
    """
    if abs(v_dot(a.get("axis", axis_vector("Z")), b.get("axis", axis_vector("Z")))) < X1_AXIS_PARALLEL_DOT:
        return False
    r_ref = max(float(a.get("radius", 0.0)), float(b.get("radius", 0.0)))
    if r_ref <= 1.0e-9:
        return False
    # Need meaningfully different radii; otherwise regular duplicate fusion has
    # already handled it.
    if abs(float(a.get("radius", 0.0)) - float(b.get("radius", 0.0))) < max(0.12, r_ref * 0.18):
        return False
    center_tol = max(X1_CENTER_ABS_TOL, r_ref * X1_CENTER_RADIUS_FACTOR)
    if line_distance_parallel(a.get("base", a["start"]), a["axis"], b.get("base", b["start"]), b["axis"]) > center_tol:
        return False
    axis = canonical_axis(a["axis"])
    a0, a1 = primitive_axis_interval(a, axis)
    b0, b1 = primitive_axis_interval(b, axis)
    allowed_gap = max(1.00, r_ref * 0.45)
    if interval_gap(a0, a1, b0, b1) > allowed_gap:
        return False
    return True


def annotate_stepped_relations(primitives):
    """Annotate accepted primitives that look like multi-radius feature stacks.

    R3 already finds many counterbore-like cases as two correct cylinders: a
    wide shallow segment and a smaller deeper segment.  R5 keeps both cylinders
    but labels the relationship so the output is more useful and closer to the
    older NEU15 profile-classification ideas.
    """
    if not X1_ANNOTATE_STEPPED_STACKS:
        return []
    n = len(primitives)
    if n < 2:
        return []
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if primitives_coaxial_for_stack(primitives[i], primitives[j]):
                union(i, j)

    comps = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)

    stack_infos = []
    stack_id = 1
    for indices in comps.values():
        if len(indices) < 2:
            continue
        ordered = sorted(indices, key=lambda idx: -float(primitives[idx].get("radius", 0.0)))
        max_r = float(primitives[ordered[0]].get("radius", 0.0))
        min_r = float(primitives[ordered[-1]].get("radius", 0.0))
        axis_name = primitives[ordered[0]].get("axis_hint", "FREE")
        for rank, idx in enumerate(ordered):
            p = primitives[idx]
            base_profile = str(p.get("profile", "BORE"))
            if "STACK_" not in base_profile:
                role = "STACK_OUTER_COUNTERBORE_SEGMENT" if rank == 0 else "STACK_INNER_CORE_SEGMENT"
                p["profile"] = "%s | %s_%02d" % (base_profile, role, stack_id)
            p["stack_id"] = stack_id
            p["stack_size"] = len(indices)
        stack_infos.append({"id": stack_id, "axis": axis_name, "segments": len(indices), "max_radius": max_r, "min_radius": min_r})
        stack_id += 1
    return stack_infos


def observation_usage_report(observations, primitives):
    """Count which observations actually drive accepted geometry."""
    used_sources = set()
    for prim in primitives:
        for obs in prim.get("observations", []):
            used_sources.add(obs.get("source", "?"))

    def count_where(items, pred):
        return sum(1 for item in items if pred(item))

    inner_total = count_where(observations, lambda o: o.get("is_inner_wire"))
    weak_total = count_where(observations, lambda o: o.get("kind") == "ring" and not o.get("is_inner_wire") and not o.get("is_analytic"))
    analytic_total = count_where(observations, lambda o: o.get("is_analytic"))
    cyl_total = count_where(observations, lambda o: o.get("kind") == "cylinder_face")

    inner_used = count_where(observations, lambda o: o.get("is_inner_wire") and o.get("source", "?") in used_sources)
    weak_used = count_where(observations, lambda o: o.get("kind") == "ring" and not o.get("is_inner_wire") and not o.get("is_analytic") and o.get("source", "?") in used_sources)
    analytic_used = count_where(observations, lambda o: o.get("is_analytic") and o.get("source", "?") in used_sources)
    cyl_used = count_where(observations, lambda o: o.get("kind") == "cylinder_face" and o.get("source", "?") in used_sources)

    return {
        "inner_total": inner_total,
        "inner_used": inner_used,
        "weak_total": weak_total,
        "weak_used": weak_used,
        "analytic_total": analytic_total,
        "analytic_used": analytic_used,
        "cyl_total": cyl_total,
        "cyl_used": cyl_used,
    }


def primitive_breakdown(primitives):
    axes = {"X": 0, "Y": 0, "Z": 0, "FREE": 0}
    profiles = {}
    for p in primitives:
        ax = p.get("axis_hint", "FREE")
        if ax not in axes:
            ax = "FREE"
        axes[ax] += 1
        prof = str(p.get("profile", "BORE"))
        # Keep the summary readable by trimming stack suffixes.
        prof_key = prof.split(" | ")[0]
        profiles[prof_key] = profiles.get(prof_key, 0) + 1
    return axes, profiles


def add_custom_text_property(obj, prop_name, value):
    """Attach useful metadata without failing older FreeCAD builds."""
    try:
        if not hasattr(obj, prop_name):
            obj.addProperty("App::PropertyString", prop_name, "X1_2026", "X1 generated metadata")
        setattr(obj, prop_name, str(value))
    except Exception:
        pass


def add_common_feature_metadata(obj, *, family, role, stage, kind="diagnostic", profile=None):
    """R18G metadata helper.

    The geometry/detection path is intentionally unchanged from R17.  This helper
    only adds normalized metadata so downstream tools can consume the generated
    feature markers without parsing labels or console text.
    """
    add_custom_text_property(obj, "X1_Checkpoint", X1_VERSION)
    add_custom_text_property(obj, "X1_FeatureFamily", family)
    add_custom_text_property(obj, "X1_FeatureRole", role)
    add_custom_text_property(obj, "X1_FeatureStage", stage)
    add_custom_text_property(obj, "X1_FeatureKind", kind)
    if profile is not None:
        add_custom_text_property(obj, "X1_Profile", profile)


def add_size_pair_metadata(obj, prop_name, width, height):
    """Store paired dimensions in a readable, stable text format."""
    add_custom_text_property(obj, prop_name, "%.6f x %.6f" % (float(width), float(height)))


# =============================================================================
# R8 missing-pocket diagnostics
# =============================================================================


def compact_source_name(source, max_len=120):
    """Readable source identifier for console logs.

    Earlier R18 console output sometimes became ambiguous when long object labels
    were sliced from the left. R20B keeps the important object/context prefix and
    the local wire id, only middle-ellipsizing when a line would become too long.
    """
    try:
        text = str(source)
    except Exception:
        return str(source)
    if len(text) <= int(max_len):
        return text
    keep_left = max(32, int(max_len * 0.58))
    keep_right = max(24, int(max_len) - keep_left - 3)
    return text[:keep_left] + "..." + text[-keep_right:]


def nearest_accepted_relation(obs, primitives):
    """Return distance/radius relation to the nearest accepted primitive.

    This does not accept or reject anything by itself.  It is diagnostic only and
    helps identify whether a rejected one-ring candidate is near an already found
    counterbore/through-bore stack or is isolated.
    """
    if not primitives:
        return None
    best = None
    for prim in primitives:
        if abs(v_dot(obs.get("axis", axis_vector("Z")), prim.get("axis", axis_vector("Z")))) < X1_AXIS_PARALLEL_DOT:
            continue
        dist = line_distance_parallel(obs.get("center", v_new(0, 0, 0)), obs.get("axis", axis_vector("Z")), prim.get("base", prim.get("start", v_new(0, 0, 0))), prim.get("axis", axis_vector("Z")))
        radius_delta = abs(float(obs.get("radius", 0.0)) - float(prim.get("radius", 0.0)))
        radius_ratio = float(obs.get("radius", 0.0)) / max(float(prim.get("radius", 0.0)), 1.0e-9)
        item = {
            "dist": dist,
            "axis": prim.get("axis_hint", "FREE"),
            "radius": float(prim.get("radius", 0.0)),
            "radius_delta": radius_delta,
            "radius_ratio": radius_ratio,
            "profile": prim.get("profile", "BORE"),
        }
        if best is None or item["dist"] < best["dist"]:
            best = item
    return best


def pocket_candidate_score(group, reason, bb, accepted_primitives):
    """Score one rejected group as a possible missing pocket.

    The score is deliberately used only for a printed ranking.  R4 showed that
    drawing these candidates as geometry creates false positives.  R7/R8/R9/R10/R11/R18G therefore
    keeps them as console evidence until a safer pocket rule is proven.
    """
    robs = group.get("observations", [])
    if len(robs) != 1:
        return None
    obs = robs[0]
    if obs.get("kind") != "ring":
        return None
    reason_text = str(reason)
    if "only one ring" not in reason_text:
        return None
    if "large unknown outer" in reason_text:
        return None

    axis_name = axis_hint(obs.get("axis", axis_vector("Z")))
    radius = float(obs.get("radius", 0.0))
    if radius < X1_MIN_RADIUS:
        return None
    span = cross_section_span_for_axis(bb, axis_name) if bb is not None else 0.0
    radius_fraction = radius / max(span, 1.0e-9) if span > 1.0e-9 else 0.0
    if span > 1.0e-9 and radius_fraction > X1_POCKET_DIAGNOSTIC_MAX_RADIUS_FRACTION:
        # Keep the diagnostic list focused.  Huge one-ring groups were the main
        # R4 false-positive source.
        return None

    point_count = int(obs.get("point_count", 0))
    rel_rms = float(obs.get("rel_rms", 1.0))
    inner = bool(obs.get("is_inner_wire"))
    analytic = bool(obs.get("is_analytic"))
    weak = not inner and not analytic

    score = 0.0
    tags = []
    if inner:
        score += 4.0
        tags.append("inner_wire")
    elif analytic:
        score += 3.0
        tags.append("analytic_ring")
    else:
        score += 1.0
        tags.append("weak_closed_wire")

    # Clean circular fit is useful, but not enough to promote a pocket.
    if rel_rms <= 0.015:
        score += 1.2
        tags.append("very_clean_fit")
    elif rel_rms <= 0.035:
        score += 0.7
        tags.append("clean_fit")
    elif rel_rms <= X1_MAX_RING_REL_RMS:
        score += 0.25
        tags.append("acceptable_fit")

    if point_count >= 20:
        score += 0.8
        tags.append("many_points")
    elif point_count >= 10:
        score += 0.35
        tags.append("some_points")

    if span > 1.0e-9:
        if radius_fraction <= 0.08:
            score += 0.7
            tags.append("small_vs_part")
        elif radius_fraction <= 0.14:
            score += 0.35
            tags.append("moderate_vs_part")
        else:
            score -= 0.6
            tags.append("large_vs_part")

    nearest = nearest_accepted_relation(obs, accepted_primitives)
    if nearest is not None:
        near_limit = max(X1_CENTER_ABS_TOL, radius * 0.75, nearest.get("radius", 0.0) * 0.35)
        if nearest["dist"] <= near_limit:
            # Near an accepted stack can mean a missed pocket tier/chamfer, or it
            # can mean duplicate decorative/edge evidence.  Mark it, but do not
            # over-reward it.
            score += 0.35
            tags.append("near_accepted_stack")
        else:
            tags.append("isolated")
    else:
        tags.append("no_accepted_neighbor")

    if weak:
        # R4 proved weak one-ring candidates are dangerous.  Penalize them so
        # only very clean, reasonably sized ones reach the printed top list.
        score -= 0.45

    if score < X1_POCKET_DIAGNOSTIC_MIN_SCORE:
        return None

    return {
        "score": score,
        "axis": axis_name,
        "center": obs.get("center", v_new(0, 0, 0)),
        "radius": radius,
        "radius_fraction": radius_fraction,
        "source": compact_source_name(obs.get("source", "?")),
        "reason": reason_text,
        "point_count": point_count,
        "rel_rms": rel_rms,
        "tags": tags,
        "nearest": nearest,
        "points": list(obs.get("points", [])),
        "observation_axis": axis_name,
    }


def pocket_diagnostic_candidates(rejected, bb, accepted_primitives):
    candidates = []
    for group, reason in rejected:
        cand = pocket_candidate_score(group, reason, bb, accepted_primitives)
        if cand is not None:
            candidates.append(cand)
    candidates.sort(key=lambda c: (-c.get("score", 0.0), c.get("axis", ""), c.get("radius", 0.0)))
    return candidates



def candidate_center_distance_for_region(a, b):
    """Distance used by the R7/R8/R9/R10/R11/R18G physical-region grouping.

    Pocket suspects can appear with different axis guesses for the same physical
    location, especially when a closed decorative/edge wire is observed on a
    side wall.  Therefore R7/R8/R9/R10/R11/R18G clusters by 3D center proximity first and reports
    the axis mix instead of forcing one axis too early.
    """
    return v_dist(a.get("center", v_new(0, 0, 0)), b.get("center", v_new(0, 0, 0)))


def same_pocket_region(a, b):
    ra = float(a.get("radius", 0.0))
    rb = float(b.get("radius", 0.0))
    tol = max(
        X1_POCKET_REGION_CLUSTER_ABS_TOL,
        X1_POCKET_REGION_CLUSTER_RADIUS_FACTOR * max(ra, rb, 1.0),
    )
    if candidate_center_distance_for_region(a, b) > tol:
        return False
    # Avoid merging tiny screw/pin suspects with large broad silhouette rings
    # that happen to share a nearby center.
    small = min(max(ra, 1.0e-9), max(rb, 1.0e-9))
    large = max(ra, rb)
    if large / small > 4.25:
        return False
    return True


def pocket_region_summary(members):
    """Summarize a cluster of pocket suspects for console diagnostics."""
    if not members:
        return None
    total_weight = sum(max(0.1, float(m.get("score", 0.0))) for m in members)
    sx = sy = sz = sr = ss = 0.0
    for m in members:
        w = max(0.1, float(m.get("score", 0.0)))
        c = m.get("center", v_new(0, 0, 0))
        sx += c.x * w
        sy += c.y * w
        sz += c.z * w
        sr += float(m.get("radius", 0.0)) * w
        ss += float(m.get("score", 0.0))
    center = v_new(sx / total_weight, sy / total_weight, sz / total_weight)
    radius = sr / total_weight
    # Compact axis/source/tag statistics.
    axes = {}
    sources = []
    tags = {}
    region_points = []
    for m in members:
        axes[m.get("axis", "?")] = axes.get(m.get("axis", "?"), 0) + 1
        sources.append(str(m.get("source", "?")))
        region_points.extend(list(m.get("points", [])))
        for tag in m.get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1
    spread = max(candidate_center_distance_for_region({"center": center}, m) for m in members)
    axis_text = ",".join("%s:%d" % (k, axes[k]) for k in sorted(axes.keys()))
    # Prefer meaningful/common tags first.
    tag_items = sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    tag_text = "+".join("%s:%d" % (k, v) for k, v in tag_items)
    return {
        "members": members,
        "count": len(members),
        "score": ss,
        "avg_score": ss / max(1, len(members)),
        "center": center,
        "radius": radius,
        "spread": spread,
        "axes": axis_text,
        "tags": tag_text,
        "sources": sorted(set(sources)),
        "points": region_points,
    }


def cluster_pocket_regions(candidates):
    """Cluster ranked one-ring suspects into likely physical pocket regions.

    This is diagnostic only.  It intentionally does not promote regions to real
    bore/pocket primitives.  A future R8 can add a very small visual marker only
    after a region rule is proven on more parts.
    """
    clusters = []
    # Start with highest scoring candidates so cluster centers are seeded by
    # the cleanest evidence first.
    for cand in sorted(candidates, key=lambda c: -float(c.get("score", 0.0))):
        best_cluster = None
        best_dist = None
        for cluster in clusters:
            # Compare against all members instead of only the centroid so local
            # multi-wire arcs can grow naturally.
            local_best = min(candidate_center_distance_for_region(cand, member) for member in cluster)
            if any(same_pocket_region(cand, member) for member in cluster):
                if best_dist is None or local_best < best_dist:
                    best_dist = local_best
                    best_cluster = cluster
        if best_cluster is None:
            clusters.append([cand])
        else:
            best_cluster.append(cand)
    summaries = []
    for cluster in clusters:
        summary = pocket_region_summary(cluster)
        if summary is None:
            continue
        if summary["count"] < X1_POCKET_REGION_MIN_MEMBERS:
            continue
        if summary["score"] < X1_POCKET_REGION_MIN_SCORE:
            continue
        summaries.append(summary)
    summaries.sort(key=lambda r: (-r.get("score", 0.0), -r.get("count", 0), r.get("radius", 0.0)))
    return summaries


def print_pocket_region_diagnostics(candidates):
    """Print R7/R8/R9/R10/R11/R18G pocket-region clusters. Geometry creation is handled separately by the guarded R8 marker emitter."""
    if not X1_PRINT_POCKET_REGION_DIAGNOSTICS:
        return []
    regions = cluster_pocket_regions(candidates)
    x1_msg("    pocket-region clusters: %d shown of %d" % (min(len(regions), X1_MAX_POCKET_REGION_LINES), len(regions)))
    if not regions:
        x1_msg("      no multi-suspect pocket regions passed the R7/R8/R9/R10/R11/R18G cluster filter")
        return []
    for idx, region in enumerate(regions[:X1_MAX_POCKET_REGION_LINES], start=1):
        src = ",".join(region.get("sources", [])[:4])
        if len(region.get("sources", [])) > 4:
            src += ",..."
        x1_msg(
            "      pocket region %02d: score=%.2f members=%d avg=%.2f center=%s r_avg=%.4f spread=%.3f axes=%s tags=%s sources=%s" % (
                idx,
                region.get("score", 0.0),
                region.get("count", 0),
                region.get("avg_score", 0.0),
                vec_to_text(region.get("center", v_new(0, 0, 0))),
                region.get("radius", 0.0),
                region.get("spread", 0.0),
                region.get("axes", ""),
                region.get("tags", ""),
                src,
            )
        )
    if len(regions) > X1_MAX_POCKET_REGION_LINES:
        x1_msg("      ... %d more pocket regions hidden by limit" % (len(regions) - X1_MAX_POCKET_REGION_LINES))
    return regions


def print_missing_pocket_diagnostics(rejected, bb, accepted_primitives):
    """Print ranked pocket suspects without changing the FreeCAD document."""
    if not X1_PRINT_MISSING_POCKET_DIAGNOSTICS:
        return {"candidates": [], "regions": []}
    candidates = pocket_diagnostic_candidates(rejected, bb, accepted_primitives)
    x1_msg("  missing-pocket diagnostics: console ranking; R20B may emit anchored guarded region markers separately")
    if not candidates:
        x1_msg("    no one-ring pocket suspects passed the R8 diagnostic filter")
        return {"candidates": [], "regions": []}
    x1_msg("    ranked pocket suspects: %d shown of %d" % (min(len(candidates), X1_MAX_POCKET_DIAGNOSTIC_LINES), len(candidates)))
    regions = print_pocket_region_diagnostics(candidates)
    for idx, cand in enumerate(candidates[:X1_MAX_POCKET_DIAGNOSTIC_LINES], start=1):
        nearest = cand.get("nearest")
        if nearest is None:
            near_text = "nearest=none"
        else:
            near_text = "nearest_axis=%s nearest_r=%.3f centerline_dist=%.3f r_ratio=%.2f" % (
                nearest.get("axis", "?"), nearest.get("radius", 0.0), nearest.get("dist", 0.0), nearest.get("radius_ratio", 0.0)
            )
        x1_msg(
            "    pocket suspect %02d: score=%.2f axis=%s r=%.4f r_frac=%.3f center=%s pts=%d rms=%.4f source=%s tags=%s %s" % (
                idx,
                cand.get("score", 0.0),
                cand.get("axis", "?"),
                cand.get("radius", 0.0),
                cand.get("radius_fraction", 0.0),
                vec_to_text(cand.get("center", v_new(0, 0, 0))),
                cand.get("point_count", 0),
                cand.get("rel_rms", 0.0),
                cand.get("source", "?"),
                "+".join(cand.get("tags", [])),
                near_text,
            )
        )
    if len(candidates) > X1_MAX_POCKET_DIAGNOSTIC_LINES:
        x1_msg("    ... %d more pocket suspects hidden by limit" % (len(candidates) - X1_MAX_POCKET_DIAGNOSTIC_LINES))
    return {"candidates": candidates, "regions": regions}


# =============================================================================
# FreeCAD object creation
# =============================================================================


def ensure_group(doc, name):
    try:
        old = doc.getObject(name)
        if old is not None:
            return old
    except Exception:
        pass
    try:
        return doc.addObject("App::DocumentObjectGroup", name)
    except Exception:
        return None


def add_to_group(group, obj):
    if group is None or obj is None:
        return
    try:
        group.addObject(obj)
    except Exception:
        pass


def ensure_named_child_group(doc, parent_group, suffix, label):
    """Return a stable child group with a clean label.

    FreeCAD object names must be unique document-wide, so the internal name is
    based on the parent object group plus a suffix.  The visible Label stays
    short and readable.  This is R20B's main change: it organizes already
    emitted feature objects without changing the detection pipeline.
    """
    parent_name = str(getattr(parent_group, "Name", "X1_R20B_Object"))
    safe_suffix = str(suffix).replace(" ", "_")
    group = ensure_group(doc, "%s_%s" % (parent_name, safe_suffix))
    if group is not None:
        try:
            group.Label = label
        except Exception:
            pass
        add_to_group(parent_group, group)
    return group


def build_feature_tree_groups(doc, object_group):
    """Create the R20B per-object feature taxonomy.

    The keys are intentionally semantic, because FAR Mesh can later consume the
    tree by group role rather than by parsing mixed diagnostic labels.
    """
    groups = {
        "accepted_bores": ensure_named_child_group(doc, object_group, "01_Accepted_Bores", "01 Accepted Bores"),
        "anchored_circular_pockets": ensure_named_child_group(doc, object_group, "02_Anchored_Circular_Pockets", "02 Anchored Circular Pockets"),
        "hex_nut_mouth_diagnostics": ensure_named_child_group(doc, object_group, "03_Hex_Nut_Mouth_Diagnostics", "03 Hex / Nut Mouth Diagnostics"),
        "hex_nut_chamfer_resolved_seats": ensure_named_child_group(doc, object_group, "04_Hex_Nut_Chamfer_Resolved_Seats", "04 Hex / Nut Chamfer-Resolved Seats"),
        "fast_tessellation_diagnostics": ensure_named_child_group(doc, object_group, "05_FAST_Tessellation_Diagnostics", "05 FAST Tessellation / Chamfer Diagnostics"),
        "chamfer_aware_reconciliation": ensure_named_child_group(doc, object_group, "06_Chamfer_Aware_Reconciliation", "06 Chamfer-Aware Reconciliation"),
        "tessellated_axis_side_probe": ensure_named_child_group(doc, object_group, "07_Tessellated_Axis_Side_Probe", "07 Tessellated Axis-Side Probe"),
        "consolidated_tessellated_ledger": ensure_named_child_group(doc, object_group, "08_Consolidated_Tessellated_Ledger", "08 Consolidated Tessellated Ledger"),
        "rejected_diagnostics": ensure_named_child_group(doc, object_group, "90_Rejected_Diagnostics", "90 Rejected / Debug Diagnostics"),
    }
    return groups


def color_for_axis(axis_name):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return (1.0, 0.0, 0.0)
    if axis_name == "Y":
        return (0.0, 0.75, 0.0)
    if axis_name == "Z":
        return (0.0, 0.20, 1.0)
    return (1.0, 0.85, 0.10)


def placement_is_identity(pl):
    try:
        base = pl.Base
        if abs(float(base.x)) > 1.0e-9 or abs(float(base.y)) > 1.0e-9 or abs(float(base.z)) > 1.0e-9:
            return False
        try:
            if abs(float(pl.Rotation.Angle)) > 1.0e-9:
                return False
        except Exception:
            pass
        return True
    except Exception:
        return True


def copy_source_placement_if_needed(out_obj, source_obj):
    if not X1_COPY_SOURCE_PLACEMENT_TO_OUTPUT:
        return False
    try:
        pl = getattr(source_obj, "Placement", None)
        if pl is None:
            return False
        out_obj.Placement = pl
        return not placement_is_identity(pl)
    except Exception:
        return False


def emit_cylinder(doc, group, primitive, index, source_obj):
    radius = float(primitive["radius"])
    start = primitive["start"]
    end = primitive["end"]
    direction = v_sub(end, start)
    height = v_len(direction)
    if height <= 1.0e-9:
        return None
    direction = v_unit(direction)
    try:
        shape = Part.makeCylinder(radius, height, start, direction)
        obj = doc.addObject("Part::Feature", "X1_R20B_Bore_%03d" % index)
        obj.Shape = shape
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = "X1 R20B bore %03d | axis=%s | %s | d=%.3f | h=%.3f | c=%.2f" % (
            index,
            primitive.get("axis_hint", "FREE"),
            primitive.get("profile", "BORE"),
            primitive.get("diameter", 0.0),
            height,
            primitive.get("confidence", 0.0),
        )
        add_custom_text_property(obj, "X1_Profile", primitive.get("profile", "BORE"))
        add_custom_text_property(obj, "X1_Axis", primitive.get("axis_hint", "FREE"))
        add_custom_text_property(obj, "X1_Diameter", "%.6f" % primitive.get("diameter", 0.0))
        add_custom_text_property(obj, "X1_Confidence", "%.6f" % primitive.get("confidence", 0.0))
        if primitive.get("stack_id") is not None:
            add_custom_text_property(obj, "X1_StackId", primitive.get("stack_id"))
        try:
            obj.ViewObject.ShapeColor = color_for_axis(primitive.get("axis_hint", "FREE"))
            obj.ViewObject.Transparency = int(X1_CYLINDER_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_to_group(group, obj)
        if X1_PRINT_ACCEPTED_DETAILS:
            x1_msg(
                "  X1 R20B cylinder %03d: axis=%s color=%s radius=%.4f height=%.4f start=%s end=%s conf=%.3f rings=%d inner=%d analytic=%d cylfaces=%d unknown=%d placement_copied=%s profile=%s" % (
                    index,
                    primitive.get("axis_hint", "FREE"),
                    str(color_for_axis(primitive.get("axis_hint", "FREE"))),
                    radius,
                    height,
                    vec_to_text(start),
                    vec_to_text(end),
                    primitive.get("confidence", 0.0),
                    primitive.get("ring_count", 0),
                    primitive.get("inner_ring_count", 0),
                    primitive.get("analytic_ring_count", 0),
                    primitive.get("cylinder_face_count", 0),
                    primitive.get("unknown_ring_count", 0),
                    str(copied),
                    primitive.get("profile", "BORE"),
                )
            )
        return obj
    except Exception as exc:
        x1_warn("failed to emit cylinder %d: %s" % (index, exc))
        return None



def parse_axis_counts_text(axis_text):
    """Parse a compact axis count string such as 'Y:7' or 'Y:4,Z:2'."""
    counts = {}
    for part in str(axis_text or "").split(','):
        part = part.strip()
        if not part or ':' not in part:
            continue
        key, value = part.split(':', 1)
        try:
            counts[key.strip().upper()] = int(value)
        except Exception:
            pass
    return counts


def dominant_axis_from_region(region):
    counts = parse_axis_counts_text(region.get("axes", ""))
    if not counts:
        return "FREE", 0, 0
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    dominant_axis, dominant_count = items[0]
    other_count = sum(v for k, v in counts.items() if k != dominant_axis)
    if dominant_axis not in ("X", "Y", "Z"):
        dominant_axis = "FREE"
    return dominant_axis, dominant_count, other_count


def region_radius_fraction(region, bb):
    axis_name, _, _ = dominant_axis_from_region(region)
    if bb is None:
        return 0.0
    span = cross_section_span_for_axis(bb, axis_name)
    if span <= 1.0e-9:
        return 0.0
    return float(region.get("radius", 0.0)) / span


def is_strong_pocket_region(region, bb):
    """Return True only for strong repeated pocket-region clusters.

    This guard intentionally rejects the R7 small/mixed-axis clusters and the
    smaller three-member side fragments.  It is a visual confirmation rule, not
    a final feature-recognition acceptance rule.
    """
    if int(region.get("count", 0)) < X1_STRONG_POCKET_REGION_MIN_MEMBERS:
        return False
    if float(region.get("score", 0.0)) < X1_STRONG_POCKET_REGION_MIN_SCORE:
        return False
    axis_name, dominant_count, other_count = dominant_axis_from_region(region)
    if axis_name == "FREE":
        return False
    if dominant_count < X1_STRONG_POCKET_REGION_MIN_DOMINANT_AXIS_COUNT:
        return False
    if other_count > X1_STRONG_POCKET_REGION_MAX_AXIS_MIX:
        return False
    radius = float(region.get("radius", 0.0))
    spread = float(region.get("spread", 0.0))
    if radius <= X1_MIN_RADIUS:
        return False
    max_spread = min(
        X1_STRONG_POCKET_REGION_MAX_SPREAD_ABS,
        max(1.5, X1_STRONG_POCKET_REGION_MAX_SPREAD_RADIUS_FACTOR * radius),
    )
    if spread > max_spread:
        return False
    rf = region_radius_fraction(region, bb)
    if rf > 0.0:
        if rf < X1_STRONG_POCKET_REGION_MIN_RADIUS_FRACTION:
            return False
        if rf > X1_STRONG_POCKET_REGION_MAX_RADIUS_FRACTION:
            return False
    return True



def clamp_value(x, lo, hi):
    return max(lo, min(hi, x))


def primitive_start_end_axis(primitive):
    """Return (start, end, axis, height) for an accepted primitive."""
    try:
        start = primitive.get("start")
        end = primitive.get("end")
        axis = primitive.get("axis")
        if start is None or end is None:
            base = primitive.get("base")
            height = float(primitive.get("height", 0.0))
            if base is None or axis is None or height <= 1.0e-9:
                return None
            axis = v_unit(axis)
            return base, v_add(base, v_scale(axis, height)), axis, height
        axis = v_unit(v_sub(end, start)) if axis is None else v_unit(axis)
        height = v_dist(start, end)
        if height <= 1.0e-9:
            return None
        return start, end, axis, height
    except Exception:
        return None


def context_for_pocket_region(region, accepted_primitives):
    """Find a nearby accepted bore that can supply the true marker axis.

    This is deliberately diagnostic-only.  It does not accept a new bore and it
    does not change the stable R5/R6/R7/R8/R9/R10/R11/R18G detection path.  It only corrects
    the orientation/centerline of a pocket-region marker when the clustered
    weak-wire region is geometrically close to an already accepted bore line.
    """
    if not X1_R10_CONTEXT_AXIS_OVERRIDE_ENABLED:
        return None
    center = region.get("center", v_new(0, 0, 0))
    radius = float(region.get("radius", 0.0))
    if radius <= X1_MIN_RADIUS:
        return None

    best = None
    for prim in accepted_primitives or []:
        axis_name = str(prim.get("axis_hint", "FREE")).upper()
        if axis_name not in ("X", "Y", "Z"):
            continue
        data = primitive_start_end_axis(prim)
        if data is None:
            continue
        start, end, axis, height = data
        prim_radius = float(prim.get("radius", 0.0))
        if prim_radius <= X1_MIN_RADIUS:
            continue

        rel = v_sub(center, start)
        t = v_dot(rel, axis)
        projected_infinite = v_add(start, v_scale(axis, t))
        projected_segment = v_add(start, v_scale(axis, clamp_value(t, 0.0, height)))
        cross_distance = v_dist(center, projected_infinite)
        axial_extra = max(0.0, -t, t - height)

        cross_limit = max(
            X1_CENTER_ABS_TOL,
            radius * X1_R10_CONTEXT_CROSS_DISTANCE_FACTOR,
            prim_radius * X1_R10_CONTEXT_PRIMITIVE_RADIUS_FACTOR,
        )
        axial_limit = max(
            2.0,
            radius * X1_R10_CONTEXT_AXIAL_EXTRA_FACTOR,
            prim_radius * X1_R10_CONTEXT_PRIMITIVE_AXIAL_FACTOR,
        )
        if cross_distance > cross_limit:
            continue
        if axial_extra > axial_limit:
            continue

        # Prefer small normalized cross distance, then small axial overshoot,
        # then higher-confidence primitives. This stays geometric, not
        # parameter-fitted to any one part.
        score = (cross_distance / max(cross_limit, 1.0e-9)) + 0.50 * (axial_extra / max(axial_limit, 1.0e-9))
        score -= 0.05 * float(prim.get("confidence", 0.0))
        item = {
            "axis_name": axis_name,
            "axis": axis,
            "center": projected_infinite,
            "segment_center": projected_segment,
            "cross_distance": cross_distance,
            "cross_limit": cross_limit,
            "axial_extra": axial_extra,
            "axial_limit": axial_limit,
            "primitive_radius": prim_radius,
            "primitive_profile": prim.get("profile", "BORE"),
            "primitive_axis": axis_name,
            "score": score,
        }
        if best is None or item["score"] < best["score"]:
            best = item
    return best


def marker_axis_and_center_for_region(region, accepted_primitives):
    """Return marker axis/center and explanation for R9/R10 diagnostic marker output."""
    region_axis_name, dominant_count, other_count = dominant_axis_from_region(region)
    region_axis = axis_vector(region_axis_name)
    region_center = region.get("center", v_new(0, 0, 0))
    context = context_for_pocket_region(region, accepted_primitives)
    if context is not None:
        return {
            "axis_name": context["axis_name"],
            "axis": context["axis"],
            "center": context["center"],
            "source": "accepted_bore_context",
            "region_axis_name": region_axis_name,
            "dominant_count": dominant_count,
            "other_count": other_count,
            "context": context,
        }
    return {
        "axis_name": region_axis_name,
        "axis": region_axis,
        "center": region_center,
        "source": "region_dominant_axis",
        "region_axis_name": region_axis_name,
        "dominant_count": dominant_count,
        "other_count": other_count,
        "context": None,
    }


def axis_span_for_marker(bb, axis_name):
    if bb is None:
        return 0.0
    try:
        if axis_name == "X":
            return float(bb.XLength)
        if axis_name == "Y":
            return float(bb.YLength)
        if axis_name == "Z":
            return float(bb.ZLength)
    except Exception:
        pass
    return 0.0



def point_line_radial_distance(point, line_center, axis):
    """Distance from a point to an infinite axis line."""
    try:
        a = canonical_axis(axis)
        rel = v_sub(point, line_center)
        axial = v_dot(rel, a)
        closest = v_add(line_center, v_scale(a, axial))
        return v_dist(point, closest)
    except Exception:
        return 0.0


def radius_band_from_distances(distances, bin_width):
    """Return the densest compact radial band from measured point distances."""
    vals = sorted(float(d) for d in distances if d is not None and float(d) > 0.0)
    if not vals:
        return None
    bin_width = max(float(bin_width), 1.0e-6)
    best = None
    i = 0
    n = len(vals)
    while i < n:
        start = vals[i]
        band = []
        j = i
        # Sliding band with width two bins; this allows mildly noisy tessellated wires.
        limit = start + 2.0 * bin_width
        while j < n and vals[j] <= limit:
            band.append(vals[j])
            j += 1
        if band:
            med = median(band)
            spread = max(band) - min(band) if len(band) > 1 else 0.0
            score = len(band) - 0.35 * (spread / max(bin_width, 1.0e-9))
            item = {"radius": med, "count": len(band), "spread": spread, "score": score, "min": min(band), "max": max(band)}
            if best is None or item["score"] > best["score"]:
                best = item
        i += 1
    return best


def projected_context_radius_estimate(region, marker, bb):
    """Estimate a context-owned pocket/counterbore radius from real wire points.

    The accepted bore context supplies the axis and centerline.  The weak pocket
    region supplies many sampled wire points.  We project those points onto the
    cross-plane of the context axis and look for the strongest radial band above
    the accepted core radius.  This remains diagnostic-only and is not tied to
    absolute coordinates of the reference part.
    """
    if not X1_R20B_RADIUS_USE_PROJECTED_POINT_BAND:
        return None
    context = marker.get("context") if marker else None
    if context is None:
        return None
    points = list(region.get("points", []))
    if len(points) < X1_R20B_PROJECTED_RADIUS_MIN_POINTS:
        return None
    axis = marker.get("axis", None)
    line_center = marker.get("center", None)
    if axis is None or line_center is None:
        return None
    core_radius = max(0.0, float(context.get("primitive_radius", 0.0)))
    region_radius = max(0.0, float(region.get("radius", 0.0)))
    cross_distance = max(0.0, float(context.get("cross_distance", 0.0)))
    min_radius = max(X1_R10_MARKER_MIN_RADIUS, core_radius * X1_R20B_PROJECTED_RADIUS_CORE_MIN_FACTOR)
    # Upper bound is intentionally loose and geometry-derived. It prevents a
    # decorative far wire from creating another huge R4-style marker but does not
    # hard-code a known diameter.
    upper_candidates = []
    if region_radius > X1_MIN_RADIUS:
        upper_candidates.append(region_radius * X1_R20B_PROJECTED_RADIUS_REGION_MAX_FACTOR)
    if cross_distance > X1_MIN_RADIUS:
        upper_candidates.append(cross_distance * X1_R20B_PROJECTED_RADIUS_CONTEXT_MAX_FACTOR)
    cross_span = cross_section_span_for_axis(bb, marker.get("axis_name", "FREE")) if bb is not None else 0.0
    if cross_span > X1_MIN_RADIUS:
        upper_candidates.append(cross_span * X1_R10_CONTEXT_RADIUS_MAX_CROSS_SECTION_FRACTION)
    max_radius = min(upper_candidates) if upper_candidates else 999999.0
    if max_radius <= min_radius:
        max_radius = max(upper_candidates) if upper_candidates else min_radius * 2.0
    distances_all = [point_line_radial_distance(p, line_center, axis) for p in points]
    distances = [d for d in distances_all if min_radius <= d <= max_radius]
    if len(distances) < X1_R20B_PROJECTED_RADIUS_MIN_BAND_POINTS:
        return {
            "usable": False,
            "reason": "not_enough_projected_distances",
            "point_count": len(points),
            "usable_count": len(distances),
            "min_radius": min_radius,
            "max_radius": max_radius,
            "raw_median": median(distances_all) if distances_all else 0.0,
        }
    raw_median = median(distances)
    bin_width = max(X1_R20B_PROJECTED_RADIUS_MIN_BIN_WIDTH, raw_median * X1_R20B_PROJECTED_RADIUS_BIN_FACTOR)
    band = radius_band_from_distances(distances, bin_width)
    if band is None or band.get("count", 0) < X1_R20B_PROJECTED_RADIUS_MIN_BAND_POINTS:
        return {
            "usable": False,
            "reason": "no_dense_projected_band",
            "point_count": len(points),
            "usable_count": len(distances),
            "min_radius": min_radius,
            "max_radius": max_radius,
            "raw_median": raw_median,
        }
    band["usable"] = True
    band["point_count"] = len(points)
    band["usable_count"] = len(distances)
    band["raw_median"] = raw_median
    band["min_radius"] = min_radius
    band["max_radius"] = max_radius
    return band

def pocket_marker_dimensions(region, marker, bb):
    """Return (radius, height, source) for a diagnostic pocket-region marker.

    R8/R9 used the clustered weak-region radius and a small visual height.  That
    proved useful for finding the four regions but too short for an X-oriented
    pocket/counterbore that lives at the end of an accepted bore.  R10 therefore
    uses accepted-bore context when available:

    - marker axis still comes from the accepted bore context;
    - marker height is based on axial_extra, so it reaches from the nearby bore
      end toward the measured pocket-region position;
    - marker radius can grow to the measured cross-distance from the bore line,
      which often represents the outer pocket shoulder better than the local
      weak-wire radius alone.

    This remains diagnostic-only and general: it uses relative distances between
    detected features, not hard-coded part coordinates.
    """
    region_radius = max(X1_R10_MARKER_MIN_RADIUS, float(region.get("radius", 0.0)))
    default_height = max(
        X1_POCKET_REGION_MARKER_MIN_HEIGHT,
        min(X1_POCKET_REGION_MARKER_MAX_HEIGHT, region_radius * X1_POCKET_REGION_MARKER_HEIGHT_FACTOR),
    )
    context = marker.get("context") if marker else None
    axis_name = marker.get("axis_name", "FREE") if marker else "FREE"
    radius = region_radius
    height = default_height
    source = "region_radius_visual_height"

    if X1_R10_CONTEXT_SIZING_ENABLED and context is not None:
        cross_distance = max(0.0, float(context.get("cross_distance", 0.0)))
        axial_extra = max(0.0, float(context.get("axial_extra", 0.0)))
        primitive_radius = max(0.0, float(context.get("primitive_radius", 0.0)))
        # R20B correction: use projected point-band radius when available.
        # This is the first radius estimate based on the actual member wire
        # points after the marker axis has been context-corrected.
        projected = projected_context_radius_estimate(region, marker, bb)
        marker["radius_debug"] = projected
        if projected is not None and projected.get("usable"):
            radius = max(X1_R10_MARKER_MIN_RADIUS, float(projected.get("radius", radius)))
            source = "context_axial_depth_and_projected_point_band_radius"
        elif X1_R11_RADIUS_USE_CONTEXT_PRIMITIVE and primitive_radius > X1_MIN_RADIUS:
            radius = max(X1_R10_MARKER_MIN_RADIUS, primitive_radius * X1_R11_CONTEXT_PRIMITIVE_RADIUS_FACTOR)
            source = "context_axial_depth_and_accepted_bore_radius"
        elif X1_R20B_FALLBACK_CORE_REGION_GEOMEAN and primitive_radius > X1_MIN_RADIUS and region_radius > primitive_radius:
            radius = math.sqrt(max(primitive_radius, X1_R10_MARKER_MIN_RADIUS) * max(region_radius, X1_R10_MARKER_MIN_RADIUS))
            source = "context_axial_depth_and_core_region_geomean_radius"
        elif X1_R10_RADIUS_USE_CONTEXT_CROSS and cross_distance > X1_MIN_RADIUS:
            radius = max(radius, cross_distance * X1_R10_CONTEXT_CROSS_RADIUS_FACTOR)
            source = "context_axial_depth_and_cross_radius"
        axis_span = axis_span_for_marker(bb, axis_name)
        max_height = X1_R10_CONTEXT_HEIGHT_MAX_ABS
        if axis_span > 1.0e-9:
            max_height = min(max_height, max(2.0, axis_span * X1_R10_CONTEXT_HEIGHT_MAX_AXIS_SPAN_FRACTION))
        if axial_extra > X1_MIN_DEPTH:
            height = max(height, axial_extra * X1_R10_CONTEXT_HEIGHT_AXIAL_EXTRA_FACTOR)
        height = max(X1_POCKET_REGION_MARKER_MIN_HEIGHT, min(max_height, height))
        # Keep context-sized radius bounded by the part cross section so a bad
        # region cannot create a huge R4-style false-positive marker.
        cross_span = cross_section_span_for_axis(bb, axis_name) if bb is not None else 0.0
        if cross_span > 1.0e-9:
            radius = min(radius, cross_span * X1_R10_CONTEXT_RADIUS_MAX_CROSS_SECTION_FRACTION)
        radius = max(X1_R10_MARKER_MIN_RADIUS, radius)
        if source == "region_radius_visual_height":
            source = "context_axial_depth_and_region_radius"
    return radius, height, source


def emit_pocket_region_marker(doc, group, region, index, source_obj, bb, accepted_primitives):
    """Create one translucent diagnostic cylinder for a strong pocket region.

    The marker is deliberately stored under a separate subgroup and labelled as
    diagnostic so it cannot be confused with the accepted bore cylinders.
    """
    marker = marker_axis_and_center_for_region(region, accepted_primitives)
    axis_name = marker["axis_name"]
    axis = marker["axis"]
    center = marker["center"]
    marker_source = marker.get("source", "region_dominant_axis")
    region_axis_name = marker.get("region_axis_name", axis_name)
    context = marker.get("context")
    raw_radius = float(region.get("radius", 0.0))
    radius, height, dimension_source = pocket_marker_dimensions(region, marker, bb)
    radius_debug = marker.get("radius_debug") if marker else None
    if X1_R20B_REQUIRE_PROJECTED_RADIUS_ANCHOR:
        if radius_debug is None or not radius_debug.get("usable"):
            x1_msg("  X1 R20B anchored pocket marker %03d skipped: no usable projected-radius anchor" % index)
            return None
        band_count = int(radius_debug.get("count", 0))
        usable_count = int(radius_debug.get("usable_count", 0))
        spread = float(radius_debug.get("spread", 0.0))
        rel_spread = spread / max(float(radius_debug.get("radius", radius)), 1.0e-9)
        context = marker.get("context") if marker else None
        primitive_radius = float(context.get("primitive_radius", 0.0)) if context is not None else 0.0
        raw_region_radius = max(float(region.get("radius", 0.0)), 1.0e-9)
        core_ratio = radius / max(primitive_radius, 1.0e-9) if primitive_radius > X1_MIN_RADIUS else 999.0
        region_ratio = radius / raw_region_radius
        if band_count < X1_R20B_RADIUS_ANCHOR_MIN_BAND_POINTS or usable_count < X1_R20B_RADIUS_ANCHOR_MIN_USABLE_POINTS or rel_spread > X1_R20B_RADIUS_ANCHOR_MAX_REL_SPREAD or core_ratio < X1_R20B_RADIUS_ANCHOR_MIN_CORE_RATIO or region_ratio > X1_R20B_RADIUS_ANCHOR_MAX_REGION_RATIO:
            x1_msg("  X1 R20B anchored pocket marker %03d skipped: weak radius anchor band=%d usable=%d rel_spread=%.4f core_ratio=%.3f region_ratio=%.3f" % (index, band_count, usable_count, rel_spread, core_ratio, region_ratio))
            return None
        marker["anchor_quality"] = {
            "band_count": band_count,
            "usable_count": usable_count,
            "rel_spread": rel_spread,
            "core_ratio": core_ratio,
            "region_ratio": region_ratio,
        }
    start = v_sub(center, v_scale(axis, height * 0.5))
    try:
        shape = Part.makeCylinder(radius, height, start, axis)
        obj = doc.addObject("Part::Feature", "X1_R20B_PocketRegion_%03d" % index)
        obj.Shape = shape
        copied = copy_source_placement_if_needed(obj, source_obj)
        rf = region_radius_fraction(region, bb)
        obj.Label = "X1 R20B DIAGNOSTIC anchored pocket %03d | axis=%s | region_axis=%s | r=%.3f | h=%.3f | members=%d | score=%.2f" % (
            index,
            axis_name,
            region_axis_name,
            radius,
            height,
            int(region.get("count", 0)),
            float(region.get("score", 0.0)),
        )
        add_custom_text_property(obj, "X1_DiagnosticOnly", "true")
        add_custom_text_property(obj, "X1_RegionType", "POCKET_REGION_MARKER")
        add_custom_text_property(obj, "X1_Axis", axis_name)
        add_custom_text_property(obj, "X1_RegionDominantAxis", region_axis_name)
        add_custom_text_property(obj, "X1_MarkerAxisSource", marker_source)
        add_custom_text_property(obj, "X1_DimensionSource", dimension_source)
        add_custom_text_property(obj, "X1_Height", "%.6f" % height)
        add_custom_text_property(obj, "X1_RawRegionRadius", "%.6f" % raw_radius)
        anchor_quality = marker.get("anchor_quality") if marker else None
        if anchor_quality is not None:
            x1_msg("    R20B anchor quality %03d: band_count=%d usable_points=%d rel_spread=%.5f core_ratio=%.3f region_ratio=%.3f" % (
                index, int(anchor_quality.get("band_count", 0)), int(anchor_quality.get("usable_count", 0)),
                float(anchor_quality.get("rel_spread", 0.0)), float(anchor_quality.get("core_ratio", 0.0)),
                float(anchor_quality.get("region_ratio", 0.0))
            ))
        radius_debug = marker.get("radius_debug") if marker else None
        if radius_debug is not None:
            add_custom_text_property(obj, "X1_RadiusEstimateUsable", str(bool(radius_debug.get("usable"))))
            add_custom_text_property(obj, "X1_RadiusEstimateCount", str(radius_debug.get("count", radius_debug.get("usable_count", 0))))
            add_custom_text_property(obj, "X1_RadiusEstimateRawMedian", "%.6f" % float(radius_debug.get("raw_median", 0.0)))
            anchor_quality = marker.get("anchor_quality") if marker else None
            if anchor_quality is not None:
                add_custom_text_property(obj, "X1_RadiusAnchorBandCount", str(anchor_quality.get("band_count", 0)))
                add_custom_text_property(obj, "X1_RadiusAnchorUsablePoints", str(anchor_quality.get("usable_count", 0)))
                add_custom_text_property(obj, "X1_RadiusAnchorRelSpread", "%.6f" % float(anchor_quality.get("rel_spread", 0.0)))
                add_custom_text_property(obj, "X1_RadiusAnchorCoreRatio", "%.6f" % float(anchor_quality.get("core_ratio", 0.0)))
                add_custom_text_property(obj, "X1_RadiusAnchorRegionRatio", "%.6f" % float(anchor_quality.get("region_ratio", 0.0)))
        add_custom_text_property(obj, "X1_RegionCenter", vec_to_text(region.get("center", v_new(0, 0, 0))))
        if context is not None:
            add_custom_text_property(obj, "X1_ContextPrimitiveAxis", context.get("primitive_axis", axis_name))
            add_custom_text_property(obj, "X1_ContextCrossDistance", "%.6f" % context.get("cross_distance", 0.0))
            add_custom_text_property(obj, "X1_ContextAxialExtra", "%.6f" % context.get("axial_extra", 0.0))
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_RadiusFraction", "%.6f" % rf)
        add_custom_text_property(obj, "X1_Members", str(int(region.get("count", 0))))
        add_custom_text_property(obj, "X1_RegionScore", "%.6f" % float(region.get("score", 0.0)))
        try:
            obj.ViewObject.ShapeColor = color_for_axis(axis_name)
            obj.ViewObject.Transparency = int(X1_POCKET_REGION_MARKER_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_to_group(group, obj)
        x1_msg(
            "  X1 R20B anchored pocket marker %03d: axis=%s region_axis=%s axis_source=%s dim_source=%s color=%s radius=%.4f raw_r=%.4f height=%.4f center=%s region_center=%s members=%d score=%.2f r_frac=%.3f placement_copied=%s%s" % (
                index,
                axis_name,
                region_axis_name,
                marker_source,
                dimension_source,
                str(color_for_axis(axis_name)),
                radius,
                raw_radius,
                height,
                vec_to_text(center),
                vec_to_text(region.get("center", v_new(0, 0, 0))),
                int(region.get("count", 0)),
                float(region.get("score", 0.0)),
                rf,
                str(copied),
                (" context_cross=%.3f context_axial_extra=%.3f" % (context.get("cross_distance", 0.0), context.get("axial_extra", 0.0))) if context is not None else "",
            )
        )
        radius_debug = marker.get("radius_debug") if marker else None
        if radius_debug is not None:
            if radius_debug.get("usable"):
                x1_msg("    R20B radius debug %03d: projected_band_radius=%.4f band_count=%d usable_points=%d/%d spread=%.4f raw_median=%.4f" % (
                    index, float(radius_debug.get("radius", 0.0)), int(radius_debug.get("count", 0)),
                    int(radius_debug.get("usable_count", 0)), int(radius_debug.get("point_count", 0)),
                    float(radius_debug.get("spread", 0.0)), float(radius_debug.get("raw_median", 0.0))
                ))
            else:
                x1_msg("    R20B radius debug %03d: projected_radius_unusable reason=%s usable_points=%d/%d raw_median=%.4f" % (
                    index, str(radius_debug.get("reason", "?")), int(radius_debug.get("usable_count", 0)),
                    int(radius_debug.get("point_count", 0)), float(radius_debug.get("raw_median", 0.0))
                ))
        return obj
    except Exception as exc:
        x1_warn("failed to emit pocket-region marker %d: %s" % (index, exc))
        return None


def emit_strong_pocket_region_markers(doc, parent_group, regions, source_obj, bb, accepted_primitives):
    """Emit guarded R9/R10 diagnostic markers for strong pocket-region clusters."""
    if not X1_EMIT_STRONG_POCKET_REGION_MARKERS:
        return 0
    strong = [r for r in regions if is_strong_pocket_region(r, bb)]
    strong.sort(key=lambda r: (-float(r.get("score", 0.0)), -int(r.get("count", 0)), vec_to_text(r.get("center", v_new(0, 0, 0)))))
    if not strong:
        x1_msg("  R20B anchored pocket markers: 0 emitted (no region passed guarded marker rule)")
        return 0
    # R18G: parent_group is already the semantic "Anchored Circular Pockets"
    # feature-family group created by build_feature_tree_groups().
    marker_group = parent_group
    emitted = 0
    for idx, region in enumerate(strong[:X1_MAX_STRONG_POCKET_REGION_MARKERS], start=1):
        try:
            marker_obj = emit_pocket_region_marker(App.ActiveDocument, marker_group, region, idx, source_obj, bb, accepted_primitives)
        except Exception as exc:
            x1_warn("  R20B pocket marker %03d skipped after diagnostic-only error: %s" % (idx, exc))
            marker_obj = None
        if marker_obj is not None:
            emitted += 1
    if len(strong) > X1_MAX_STRONG_POCKET_REGION_MARKERS:
        x1_msg("  R20B anchored pocket markers: emitted %d of %d strong regions" % (emitted, len(strong)))
    else:
        x1_msg("  R20B anchored pocket markers: emitted %d" % emitted)
    return emitted


def emit_ring_point(doc, group, obs, index, accepted=True):
    try:
        radius = max(0.20, min(1.0, obs.get("radius", 1.0) * 0.08))
        shape = Part.makeSphere(radius, obs["center"])
        obj = doc.addObject("Part::Feature", "X1_R20B_%sRing_%03d" % ("Accepted" if accepted else "Rejected", index))
        obj.Shape = shape
        obj.Label = "X1 R20B %s ring %03d | axis=%s | r=%.3f | %s" % (
            "accepted" if accepted else "rejected",
            index,
            obs.get("axis_hint", "FREE"),
            obs.get("radius", 0.0),
            obs.get("source", "?"),
        )
        try:
            obj.ViewObject.ShapeColor = color_for_axis(obs.get("axis_hint", "FREE")) if accepted else (1.0, 0.0, 0.0)
            obj.ViewObject.Transparency = 20
        except Exception:
            pass
        add_to_group(group, obj)
        return obj
    except Exception:
        return None



# =============================================================================
# R20B non-round form diagnostics: hex pockets, long slots, ellipses
# =============================================================================


def point_to_2d_for_axis(point, axis_name):
    """Project a 3D point into the local 2D plane normal to an axis hint."""
    if axis_name == "X":
        return (float(point.y), float(point.z))
    if axis_name == "Y":
        return (float(point.x), float(point.z))
    return (float(point.x), float(point.y))


def polygon_area_2d(points2d):
    if len(points2d) < 3:
        return 0.0
    area = 0.0
    n = len(points2d)
    for i in range(n):
        x1, y1 = points2d[i]
        x2, y2 = points2d[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return 0.5 * abs(area)


def polyline_perimeter_2d(points2d):
    if len(points2d) < 2:
        return 0.0
    total = 0.0
    n = len(points2d)
    for i in range(n):
        x1, y1 = points2d[i]
        x2, y2 = points2d[(i + 1) % n]
        total += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return total


def radial_stats_2d(points2d, center2d):
    cx, cy = center2d
    radii = [math.sqrt((x - cx) ** 2 + (y - cy) ** 2) for x, y in points2d]
    if not radii:
        return (0.0, 0.0, 0.0)
    mean_r = sum(radii) / float(len(radii))
    if mean_r <= 1.0e-12:
        return (0.0, 0.0, 0.0)
    var = sum((r - mean_r) ** 2 for r in radii) / float(len(radii))
    return (mean_r, math.sqrt(var), math.sqrt(var) / mean_r)


def angle_between_2d(a, b):
    ax, ay = a
    bx, by = b
    la = math.sqrt(ax * ax + ay * ay)
    lb = math.sqrt(bx * bx + by * by)
    if la <= 1.0e-12 or lb <= 1.0e-12:
        return 0.0
    c = clamp((ax * bx + ay * by) / (la * lb), -1.0, 1.0)
    return math.degrees(math.acos(c))


def estimate_corner_count_2d(points2d):
    """Count strong direction changes on the sampled wire; robust enough for diagnostics."""
    n = len(points2d)
    if n < 5:
        return 0
    # Use a stride so discretized arcs do not create dozens of tiny corners.
    stride = max(1, n // 32)
    sampled = [points2d[i] for i in range(0, n, stride)]
    if len(sampled) < 5:
        sampled = list(points2d)
    corners = 0
    m = len(sampled)
    for i in range(m):
        p0 = sampled[(i - 1) % m]
        p1 = sampled[i]
        p2 = sampled[(i + 1) % m]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        turn = 180.0 - angle_between_2d(v1, v2)
        if abs(turn) >= X1_FORM_CORNER_ANGLE_DEG:
            corners += 1
    return corners


def form_descriptor_from_wire(wire, source, strength, bb, is_inner=False):
    """Return diagnostic descriptor for a non-round closed wire, or None."""
    try:
        if not wire_is_closed(wire):
            return None
        pts = wire_points(wire, 10)
        if len(pts) < X1_FORM_MIN_POINTS:
            return None
        bb_diag_value = bbox_diag(bb)
        axis_name = plane_axis_from_points(pts, bb_diag_value)
        if axis_name is None:
            return None
        pts2d = [point_to_2d_for_axis(p, axis_name) for p in pts]
        xs = [p[0] for p in pts2d]
        ys = [p[1] for p in pts2d]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        max_dim = max(width, height)
        min_dim = min(width, height)
        if max_dim < X1_FORM_MIN_SIZE:
            return None
        if bb_diag_value > 1.0e-9 and max_dim / bb_diag_value > X1_FORM_MAX_SIZE_FRACTION:
            return None
        aspect = max_dim / max(min_dim, 1.0e-9)
        area = polygon_area_2d(pts2d)
        perimeter = polyline_perimeter_2d(pts2d)
        cx = sum(xs) / float(len(xs))
        cy = sum(ys) / float(len(ys))
        mean_r, std_r, rel_radial_std = radial_stats_2d(pts2d, (cx, cy))
        corner_count = estimate_corner_count_2d(pts2d)
        circle_rel_rms = None
        fit = fit_circle_2d(pts2d)
        if fit is not None:
            circle_rel_rms = fit[3]
        center3d = center_from_axis_and_2d(axis_name, median([v_dot(p, axis_vector(axis_name)) for p in pts]), cx, cy)
        return {
            "source": source,
            "axis": axis_name,
            "center": center3d,
            "points3d": pts,
            "points2d": pts2d,
            "wire": wire,
            "point_count": len(pts),
            "edge_count": len(list(wire.Edges)) if hasattr(wire, "Edges") else 0,
            "width": width,
            "height": height,
            "max_dim": max_dim,
            "min_dim": min_dim,
            "aspect": aspect,
            "area": area,
            "perimeter": perimeter,
            "mean_radius": mean_r,
            "rel_radial_std": rel_radial_std,
            "corner_count": corner_count,
            "circle_rel_rms": circle_rel_rms,
            "is_inner_wire": bool(is_inner),
            "strength": float(strength),
        }
    except Exception:
        return None


def classify_form_descriptor(desc):
    """Classify a non-round wire descriptor into candidate form labels."""
    labels = []
    aspect = float(desc.get("aspect", 1.0))
    corners = int(desc.get("corner_count", 0))
    edge_count = int(desc.get("edge_count", 0))
    rel_radial_std = float(desc.get("rel_radial_std", 0.0))
    circle_rel_rms = desc.get("circle_rel_rms", None)
    circle_bad = circle_rel_rms is None or float(circle_rel_rms) >= X1_FORM_CIRCLE_REL_RMS_REJECT
    inner_bonus = 0.35 if desc.get("is_inner_wire") else 0.0
    many_points_bonus = 0.20 if int(desc.get("point_count", 0)) >= 12 else 0.0

    # Hex nut pockets: compact, roughly six directional changes/edges, not a clean circle.
    hex_score = 0.0
    if X1_FORM_HEX_ASPECT_MIN <= aspect <= X1_FORM_HEX_ASPECT_MAX:
        hex_score += 0.90
    if X1_FORM_HEX_CORNER_MIN <= corners <= X1_FORM_HEX_CORNER_MAX:
        hex_score += 0.95
    if 5 <= edge_count <= 8:
        hex_score += 0.50
    if rel_radial_std < 0.18:
        hex_score += 0.25
    if circle_bad:
        hex_score += 0.25
    hex_score += inner_bonus + many_points_bonus
    if hex_score >= X1_FORM_HEX_MIN_SCORE:
        labels.append(("HEX_NUT_POCKET_CANDIDATE", hex_score))

    # Long/adjustment slots: elongated closed wire; may have arcs and straight sides.
    slot_score = 0.0
    if aspect >= X1_FORM_SLOT_ASPECT_MIN:
        slot_score += min(1.20, 0.45 + 0.25 * aspect)
    if corners <= 4:
        slot_score += 0.35
    if circle_bad:
        slot_score += 0.30
    if desc.get("point_count", 0) >= 12:
        slot_score += 0.30
    slot_score += inner_bonus
    if slot_score >= X1_FORM_SLOT_MIN_SCORE:
        labels.append(("LONG_SLOT_OR_ADJUSTABLE_BORE_CANDIDATE", slot_score))

    # Elliptical long bores: elongated but smoother than a polygon/slot, often high point count.
    ellipse_score = 0.0
    if X1_FORM_ELLIPSE_ASPECT_MIN <= aspect <= X1_FORM_ELLIPSE_ASPECT_MAX:
        ellipse_score += 0.80
    if corners <= 3:
        ellipse_score += 0.40
    if desc.get("point_count", 0) >= 14:
        ellipse_score += 0.35
    if circle_bad:
        ellipse_score += 0.30
    ellipse_score += inner_bonus
    if ellipse_score >= X1_FORM_ELLIPSE_MIN_SCORE:
        labels.append(("ELLIPTIC_OR_OVAL_BORE_CANDIDATE", ellipse_score))

    labels.sort(key=lambda item: -item[1])
    return labels


def collect_nonround_form_diagnostics(shape, label, bb):
    """Scan closed wires for diagnostic non-round forms without emitting geometry."""
    descriptors = []
    seen_sources = set()
    try:
        faces = list(shape.Faces)
    except Exception:
        faces = []
    for fi, face in enumerate(faces, start=1):
        try:
            wires = list(face.Wires)
            if len(wires) < 2:
                continue
            outer = None
            try:
                outer = face.OuterWire
            except Exception:
                pass
            lengths = [(wire_length(w), idx, w) for idx, w in enumerate(wires)]
            longest_idx = max(lengths, key=lambda x: x[0])[1] if lengths else -1
            for wi, wire in enumerate(wires, start=1):
                if outer is not None and wire_same(wire, outer):
                    continue
                if outer is None and (wi - 1) == longest_idx:
                    continue
                source = "%s:form_face_%d_inner_wire_%d" % (label, fi, wi)
                desc = form_descriptor_from_wire(wire, source, 1.0, bb, True)
                if desc is not None:
                    labels = classify_form_descriptor(desc)
                    if labels:
                        desc["labels"] = labels
                        descriptors.append(desc)
                        seen_sources.add(source)
        except Exception:
            pass
    try:
        wires = list(shape.Wires)
    except Exception:
        wires = []
    for wi, wire in enumerate(wires, start=1):
        source = "%s:form_global_closed_wire_%d" % (label, wi)
        if source in seen_sources:
            continue
        desc = form_descriptor_from_wire(wire, source, 0.55, bb, False)
        if desc is not None:
            labels = classify_form_descriptor(desc)
            if labels:
                desc["labels"] = labels
                descriptors.append(desc)
    descriptors.sort(key=lambda d: (-float(d["labels"][0][1]), -int(d.get("point_count", 0)), d.get("source", "")))
    return descriptors


def print_nonround_form_diagnostics(shape, label, bb):
    if not X1_PRINT_NONROUND_FORM_DIAGNOSTICS:
        return []
    forms = collect_nonround_form_diagnostics(shape, label, bb)
    if not forms:
        x1_msg("  R20B non-round form diagnostics: 0 candidates")
        return forms
    counts = {}
    for d in forms:
        top = d["labels"][0][0]
        counts[top] = counts.get(top, 0) + 1
    count_text = "; ".join("%s=%d" % (k, counts[k]) for k in sorted(counts.keys()))
    x1_msg("  R20B non-round form diagnostics: %d candidates (%s)" % (len(forms), count_text))
    for i, d in enumerate(forms[:X1_MAX_NONROUND_FORM_LINES], start=1):
        labels = d.get("labels", [])
        top_label, top_score = labels[0]
        alt = ",".join("%s:%.2f" % (name, score) for name, score in labels[1:3])
        if not alt:
            alt = "-"
        circle_rms = d.get("circle_rel_rms", None)
        circle_text = "None" if circle_rms is None else "%.4f" % float(circle_rms)
        x1_msg("    form %02d: %s score=%.2f axis=%s center=%s aspect=%.2f size=(%.3f x %.3f) edges=%d corners=%d pts=%d circle_rms=%s inner=%s alt=%s source=%s" % (
            i,
            top_label,
            float(top_score),
            d.get("axis", "?"),
            vec_to_text(d.get("center", v_new(0, 0, 0))),
            float(d.get("aspect", 0.0)),
            float(d.get("width", 0.0)),
            float(d.get("height", 0.0)),
            int(d.get("edge_count", 0)),
            int(d.get("corner_count", 0)),
            int(d.get("point_count", 0)),
            circle_text,
            str(bool(d.get("is_inner_wire", False))),
            alt,
            compact_source_name(d.get("source", "?")),
        ))
    remaining = len(forms) - X1_MAX_NONROUND_FORM_LINES
    if remaining > 0:
        x1_msg("    ... %d more non-round form candidates hidden by limit" % remaining)
    return forms



# =============================================================================
# R20B non-round diagnostic form markers
# =============================================================================


def color_for_form_label(label):
    """Diagnostic form-marker colors independent from bore-axis colors."""
    label = str(label)
    if label.startswith("HEX"):
        return (1.0, 0.55, 0.05)   # orange for hex / nut-pocket candidates
    if label.startswith("LONG_SLOT"):
        return (0.0, 0.85, 1.0)    # cyan for elongated slots
    if label.startswith("ELLIPTIC"):
        return (1.0, 0.85, 0.10)   # yellow for oval/ellipse candidates
    return (0.85, 0.35, 1.0)


def nonround_marker_height(desc):
    """Small marker thickness along the detected form axis."""
    max_dim = float(desc.get("max_dim", max(desc.get("width", 0.0), desc.get("height", 0.0))))
    h = max_dim * X1_NONROUND_FORM_MARKER_HEIGHT_FACTOR
    h = max(float(X1_NONROUND_FORM_MARKER_MIN_HEIGHT), h)
    h = min(float(X1_NONROUND_FORM_MARKER_MAX_HEIGHT), h)
    return h


def shape_from_form_wire(desc, height):
    """Create a translucent diagnostic prism from the original detected wire.

    This intentionally uses the footprint itself instead of replacing the form
    with a cylinder.  For hex nut pockets, the emitted marker remains hexagonal;
    for slots/ellipses it keeps the sampled closed-loop footprint as much as
    FreeCAD's Part.Face can represent it.
    """
    axis_name = desc.get("axis", "Z")
    axis = axis_vector(axis_name)
    wire = desc.get("wire")
    shape = None
    try:
        if wire is not None:
            face = Part.Face(wire)
            shape = face.extrude(v_scale(axis, height))
            try:
                shape.translate(v_scale(axis, -0.5 * height))
            except Exception:
                pass
            return shape
    except Exception:
        shape = None
    # Fallback: create a polygon from sampled points.  This is only diagnostic.
    try:
        pts = list(desc.get("points3d", []))
        if len(pts) >= 3:
            closed = list(pts)
            if v_dist(closed[0], closed[-1]) > 1.0e-8:
                closed.append(closed[0])
            poly = Part.makePolygon(closed)
            face = Part.Face(poly)
            shape = face.extrude(v_scale(axis, height))
            try:
                shape.translate(v_scale(axis, -0.5 * height))
            except Exception:
                pass
            return shape
    except Exception:
        return None
    return None


def emit_nonround_form_marker(doc, group, desc, index, source_obj):
    labels = desc.get("labels", [])
    if not labels:
        return None
    top_label, top_score = labels[0]
    if float(top_score) < X1_NONROUND_FORM_MARKER_MIN_SCORE:
        return None
    if X1_NONROUND_FORM_MARKER_INNER_ONLY and not bool(desc.get("is_inner_wire", False)):
        return None
    height = nonround_marker_height(desc)
    try:
        shape = shape_from_form_wire(desc, height)
        if shape is None:
            return None
        obj = doc.addObject("Part::Feature", "X1_R20B_FormMarker_%03d" % index)
        obj.Shape = shape
        copied = copy_source_placement_if_needed(obj, source_obj)
        axis_name = desc.get("axis", "?")
        obj.Label = "X1 R20B DIAGNOSTIC form %03d | %s | axis=%s | size=%.3f x %.3f | score=%.2f" % (
            index, top_label, axis_name, float(desc.get("width", 0.0)), float(desc.get("height", 0.0)), float(top_score)
        )
        add_custom_text_property(obj, "X1_DiagnosticOnly", "true")
        add_common_feature_metadata(
            obj,
            family="NONROUND_FORM",
            role="MOUTH_FOOTPRINT",
            stage="MOUTH",
            kind="diagnostic",
            profile=str(top_label),
        )
        add_custom_text_property(obj, "X1_FormType", str(top_label))
        add_custom_text_property(obj, "X1_FormScore", "%.6f" % float(top_score))
        add_custom_text_property(obj, "X1_Axis", str(axis_name))
        add_custom_text_property(obj, "X1_Center", vec_to_text(desc.get("center", v_new(0, 0, 0))))
        add_custom_text_property(obj, "X1_FormWidth", "%.6f" % float(desc.get("width", 0.0)))
        add_custom_text_property(obj, "X1_FormHeight", "%.6f" % float(desc.get("height", 0.0)))
        add_size_pair_metadata(obj, "X1_FormSize", float(desc.get("width", 0.0)), float(desc.get("height", 0.0)))
        add_size_pair_metadata(obj, "X1_MouthSize", float(desc.get("width", 0.0)), float(desc.get("height", 0.0)))
        add_custom_text_property(obj, "X1_FormAspect", "%.6f" % float(desc.get("aspect", 0.0)))
        add_custom_text_property(obj, "X1_FormEdges", str(int(desc.get("edge_count", 0))))
        add_custom_text_property(obj, "X1_FormCorners", str(int(desc.get("corner_count", 0))))
        add_custom_text_property(obj, "X1_FormPoints", str(int(desc.get("point_count", 0))))
        circle_rms = desc.get("circle_rel_rms", None)
        if circle_rms is not None:
            add_custom_text_property(obj, "X1_FormCircleRelRms", "%.6f" % float(circle_rms))
        add_custom_text_property(obj, "X1_Source", str(desc.get("source", "?")))
        try:
            obj.ViewObject.ShapeColor = color_for_form_label(top_label)
            obj.ViewObject.Transparency = int(X1_NONROUND_FORM_MARKER_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_to_group(group, obj)
        x1_msg("  X1 R20B form marker %03d: %s axis=%s color=%s center=%s size=(%.3f x %.3f) marker_h=%.3f score=%.2f edges=%d corners=%d pts=%d circle_rms=%s inner=%s placement_copied=%s source=%s" % (
            index,
            top_label,
            axis_name,
            str(color_for_form_label(top_label)),
            vec_to_text(desc.get("center", v_new(0, 0, 0))),
            float(desc.get("width", 0.0)),
            float(desc.get("height", 0.0)),
            height,
            float(top_score),
            int(desc.get("edge_count", 0)),
            int(desc.get("corner_count", 0)),
            int(desc.get("point_count", 0)),
            "None" if circle_rms is None else "%.4f" % float(circle_rms),
            str(bool(desc.get("is_inner_wire", False))),
            str(copied),
            compact_source_name(desc.get("source", "?")),
        ))
        return obj
    except Exception as exc:
        x1_warn("  X1 R20B form marker %03d skipped after error: %s" % (index, exc))
        return None


def emit_nonround_form_markers(doc, parent_group, forms, source_obj):
    if not X1_EMIT_NONROUND_FORM_MARKERS or not forms:
        return 0
    # R18G: parent_group is already the semantic "Hex / Nut Mouth Diagnostics"
    # feature-family group created by build_feature_tree_groups().
    marker_group = parent_group
    count = 0
    for desc in forms:
        if count >= int(X1_MAX_NONROUND_FORM_MARKERS):
            break
        marker = emit_nonround_form_marker(doc, marker_group, desc, count + 1, source_obj)
        if marker is not None:
            count += 1
    x1_msg("  R20B non-round form diagnostic markers: emitted %d" % count)
    return count


# =============================================================================
# R20B chamfer / fase diagnostics for form features
# =============================================================================


def scalar_on_axis(point, axis_name):
    """Coordinate of point along a named principal axis."""
    return v_dot(point, axis_vector(axis_name))


def cross_distance_for_axis(a, b, axis_name):
    """Distance between two points in the plane perpendicular to axis_name."""
    if axis_name == "X":
        return math.sqrt((a.y - b.y) ** 2 + (a.z - b.z) ** 2)
    if axis_name == "Y":
        return math.sqrt((a.x - b.x) ** 2 + (a.z - b.z) ** 2)
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def primitive_axis_interval(prim, axis_name):
    axis = axis_vector(axis_name)
    try:
        a = scalar_on_axis(prim.get("start"), axis_name)
        b = scalar_on_axis(prim.get("end"), axis_name)
        return (min(a, b), max(a, b))
    except Exception:
        try:
            c = scalar_on_axis(prim.get("base", prim.get("center")), axis_name)
            h = float(prim.get("height", prim.get("depth", 0.0)))
            return (c - 0.5 * h, c + 0.5 * h)
        except Exception:
            return (0.0, 0.0)


def form_context_primitives(desc, primitives):
    """Find accepted primitives coaxially near a non-round form footprint."""
    axis_name = desc.get("axis", "Z")
    center = desc.get("center", v_new(0, 0, 0))
    max_dim = float(desc.get("max_dim", max(desc.get("width", 0.0), desc.get("height", 0.0))))
    center_tol = max(float(X1_CHAMFER_CONTEXT_CENTER_MIN), max_dim * float(X1_CHAMFER_CONTEXT_CENTER_FACTOR))
    out = []
    for prim in primitives:
        if prim.get("axis_hint") != axis_name:
            continue
        try:
            base = prim.get("base", prim.get("start", center))
            cross = cross_distance_for_axis(center, base, axis_name)
            if cross > center_tol:
                continue
            t0, t1 = primitive_axis_interval(prim, axis_name)
            form_t = scalar_on_axis(center, axis_name)
            if form_t < t0:
                axial_gap = t0 - form_t
            elif form_t > t1:
                axial_gap = form_t - t1
            else:
                axial_gap = 0.0
            if axial_gap > float(X1_CHAMFER_CONTEXT_AXIS_MAX_DIST):
                continue
            out.append({
                "primitive": prim,
                "radius": float(prim.get("radius", 0.0)),
                "height": float(prim.get("height", prim.get("depth", 0.0))),
                "t0": t0,
                "t1": t1,
                "cross": cross,
                "axial_gap": axial_gap,
                "profile": prim.get("profile", "?"),
            })
        except Exception:
            continue
    out.sort(key=lambda r: (r["cross"], r["axial_gap"], -r["radius"]))
    return out


def form_nearby_ring_layers(desc, observations):
    """Find same-axis circular/wire ring layers near a form footprint."""
    axis_name = desc.get("axis", "Z")
    center = desc.get("center", v_new(0, 0, 0))
    form_t = scalar_on_axis(center, axis_name)
    max_dim = float(desc.get("max_dim", max(desc.get("width", 0.0), desc.get("height", 0.0))))
    center_tol = max(float(X1_CHAMFER_NEAR_RING_CENTER_MIN), max_dim * float(X1_CHAMFER_NEAR_RING_CENTER_FACTOR))
    out = []
    for obs in observations:
        if obs.get("kind") != "ring":
            continue
        if axis_hint(obs.get("axis", axis_vector("Z"))) != axis_name:
            continue
        try:
            c = obs.get("center", center)
            cross = cross_distance_for_axis(center, c, axis_name)
            if cross > center_tol:
                continue
            t = scalar_on_axis(c, axis_name)
            dt = t - form_t
            if abs(dt) > float(X1_CHAMFER_NEAR_RING_AXIAL_MAX):
                continue
            out.append({
                "radius": float(obs.get("radius", 0.0)),
                "t": t,
                "dt": dt,
                "cross": cross,
                "source": str(obs.get("source", "?")),
                "inner": bool(obs.get("is_inner_wire", False)),
                "analytic": bool(obs.get("is_analytic", False)),
                "strength": float(obs.get("strength", 0.0)),
            })
        except Exception:
            continue
    out.sort(key=lambda r: (abs(r["dt"]), r["cross"], -r["radius"]))
    return out


def summarize_ring_layers_for_chamfer(rings):
    """Group nearby rings by axial coordinate and summarize radius bands."""
    layers = []
    for r in rings:
        placed = False
        for layer in layers:
            if abs(float(r["dt"]) - float(layer["dt"])) <= 0.20:
                layer["items"].append(r)
                placed = True
                break
        if not placed:
            layers.append({"dt": float(r["dt"]), "items": [r]})
    result = []
    for layer in layers:
        radii = sorted(float(it["radius"]) for it in layer["items"])
        if not radii:
            continue
        result.append({
            "dt": median([float(it["dt"]) for it in layer["items"]]),
            "r_min": min(radii),
            "r_med": median(radii),
            "r_max": max(radii),
            "count": len(radii),
            "inner_count": sum(1 for it in layer["items"] if it.get("inner")),
            "sources": [compact_source_name(it.get("source", "?")) for it in layer["items"][:3]],
        })
    result.sort(key=lambda x: abs(float(x["dt"])))
    return result


def chamfer_angle_from_layers(layer_a, layer_b):
    """Estimate transition angle from two ring layers in axial/radial space."""
    dr = abs(float(layer_b.get("r_med", 0.0)) - float(layer_a.get("r_med", 0.0)))
    dz = abs(float(layer_b.get("dt", 0.0)) - float(layer_a.get("dt", 0.0)))
    if dz <= 1.0e-9 or dr <= 1.0e-9:
        return 0.0
    return math.degrees(math.atan2(dr, dz))


def analyze_form_chamfer(desc, observations, primitives):
    """Return diagnostic chamfer/fase information for one non-round form."""
    labels = desc.get("labels", [])
    if not labels:
        return None
    top_label, top_score = labels[0]
    if str(top_label) not in X1_CHAMFER_FORM_TYPES:
        return None
    axis_name = desc.get("axis", "Z")
    width = float(desc.get("width", 0.0))
    height = float(desc.get("height", 0.0))
    max_dim = float(desc.get("max_dim", max(width, height)))
    min_dim = float(desc.get("min_dim", min(width, height)))
    # For a hex footprint, half of the smaller box dimension often approximates
    # an across-flats/inradius-like mouth size; half of the larger dimension is
    # a circumradius-like mouth size.  The spread between both is a chamfer hint.
    half_min = 0.5 * min_dim
    half_max = 0.5 * max_dim
    contexts = form_context_primitives(desc, primitives)
    rings = form_nearby_ring_layers(desc, observations)
    layers = summarize_ring_layers_for_chamfer(rings)

    accepted_radii = sorted(set(round(c["radius"], 6) for c in contexts if c.get("radius", 0.0) > 0.0), reverse=True)
    outer_context = max(accepted_radii) if accepted_radii else 0.0
    inner_context = min(accepted_radii) if len(accepted_radii) >= 2 else (accepted_radii[0] if accepted_radii else 0.0)

    # Detect likely chamfered mouth when the footprint mouth is close to a larger
    # accepted outer segment and larger than the inner/core segment.
    mouth_like_outer = False
    if outer_context > 0.0 and half_min > 0.0:
        mouth_like_outer = abs(half_min - outer_context) / max(outer_context, 1.0e-9) <= 0.12
    core_smaller = inner_context > 0.0 and half_min > inner_context * (1.0 + float(X1_CHAMFER_RADIUS_STEP_MIN_RATIO))

    chamfer_angles = []
    for i in range(min(len(layers) - 1, 4)):
        angle = chamfer_angle_from_layers(layers[i], layers[i + 1])
        if float(X1_CHAMFER_ANGLE_MIN_DEG) <= angle <= float(X1_CHAMFER_ANGLE_MAX_DEG):
            chamfer_angles.append(angle)

    status = "possible_chamfered_form_mouth" if (mouth_like_outer and core_smaller) else "form_context_report"
    if not contexts and not layers:
        status = "no_nearby_chamfer_context"

    return {
        "label": top_label,
        "score": float(top_score),
        "axis": axis_name,
        "center": desc.get("center", v_new(0, 0, 0)),
        "width": width,
        "height": height,
        "half_min": half_min,
        "half_max": half_max,
        "contexts": contexts,
        "layers": layers,
        "outer_context": outer_context,
        "inner_context": inner_context,
        "mouth_like_outer": mouth_like_outer,
        "core_smaller": core_smaller,
        "chamfer_angles": chamfer_angles,
        "status": status,
        "source": desc.get("source", "?"),
        "desc": desc,
    }


def print_form_chamfer_diagnostics(forms, observations, primitives):
    """Console-only R20B chamfer/fase diagnostics for non-round form candidates."""
    if not X1_PRINT_CHAMFER_FORM_DIAGNOSTICS:
        return []
    reports = []
    for desc in forms:
        rep = analyze_form_chamfer(desc, observations, primitives)
        if rep is not None:
            reports.append(rep)
    if not reports:
        x1_msg("  R20B chamfer/fase diagnostics: 0 candidate reports")
        return reports
    x1_msg("  R20B chamfer/fase diagnostics: %d form-context reports" % len(reports))
    for i, rep in enumerate(reports[:X1_MAX_CHAMFER_FORM_LINES], start=1):
        contexts = rep.get("contexts", [])
        layers = rep.get("layers", [])
        angle_text = "-"
        if rep.get("chamfer_angles"):
            angle_text = ",".join("%.1f" % a for a in rep.get("chamfer_angles", [])[:3])
        x1_msg("    chamfer form %02d: %s status=%s axis=%s center=%s size=(%.3f x %.3f) half_min=%.3f half_max=%.3f outer_ctx=%.3f inner_ctx=%.3f mouth_like_outer=%s core_smaller=%s angles=%s source=%s" % (
            i,
            rep.get("label", "?"),
            rep.get("status", "?"),
            rep.get("axis", "?"),
            vec_to_text(rep.get("center", v_new(0, 0, 0))),
            float(rep.get("width", 0.0)),
            float(rep.get("height", 0.0)),
            float(rep.get("half_min", 0.0)),
            float(rep.get("half_max", 0.0)),
            float(rep.get("outer_context", 0.0)),
            float(rep.get("inner_context", 0.0)),
            str(bool(rep.get("mouth_like_outer", False))),
            str(bool(rep.get("core_smaller", False))),
            angle_text,
            compact_source_name(rep.get("source", "?")),
        ))
        if contexts:
            context_bits = []
            for ctx in contexts[:4]:
                context_bits.append("r=%.3f span=%.3f..%.3f h=%.3f cross=%.3f gap=%.3f profile=%s" % (
                    float(ctx.get("radius", 0.0)),
                    float(ctx.get("t0", 0.0)),
                    float(ctx.get("t1", 0.0)),
                    float(ctx.get("height", 0.0)),
                    float(ctx.get("cross", 0.0)),
                    float(ctx.get("axial_gap", 0.0)),
                    str(ctx.get("profile", "?")),
                ))
            x1_msg("      accepted context: " + " | ".join(context_bits))
        if layers:
            layer_bits = []
            for layer in layers[:5]:
                layer_bits.append("dt=%+.3f r=%.3f..%.3f..%.3f n=%d inner=%d src=%s" % (
                    float(layer.get("dt", 0.0)),
                    float(layer.get("r_min", 0.0)),
                    float(layer.get("r_med", 0.0)),
                    float(layer.get("r_max", 0.0)),
                    int(layer.get("count", 0)),
                    int(layer.get("inner_count", 0)),
                    ",".join(layer.get("sources", [])),
                ))
            x1_msg("      nearby ring layers: " + " | ".join(layer_bits))
    remaining = len(reports) - int(X1_MAX_CHAMFER_FORM_LINES)
    if remaining > 0:
        x1_msg("    ... %d more chamfer/fase form reports hidden by limit" % remaining)
    return reports


# =============================================================================
# R20B chamfer-resolved diagnostic form markers
# =============================================================================


def choose_chamfer_resolved_layer(rep):
    """Choose the first plausible smaller body/seat layer after a chamfered mouth.

    The detected non-round form footprint may be the mouth/chamfer boundary.  R16
    diagnostics summarize nearby same-axis ring layers.  For a hex nut pocket on
    the reference part this looks like:

        dt=+0   mouth-sized form layer
        dt=+7   smaller transition/body layer
        dt=+13  core bore layer

    This function picks the first non-mouth layer whose maximum radius is smaller
    than the mouth layer but still larger than the core bore radius.  It returns
    a diagnostic descriptor only; it does not promote the feature to accepted.
    """
    try:
        if str(rep.get("status", "")) != "possible_chamfered_form_mouth":
            return None
        label = str(rep.get("label", ""))
        if label not in X1_CHAMFER_RESOLVED_FORM_TYPES:
            return None
        score = float(rep.get("score", 0.0))
        if score < float(X1_CHAMFER_RESOLVED_FORM_MIN_SCORE):
            return None
        layers = list(rep.get("layers", []))
        if not layers:
            return None
        mouth_layer = min(layers, key=lambda l: abs(float(l.get("dt", 0.0))))
        mouth_r = float(mouth_layer.get("r_med", 0.0))
        if mouth_r <= 1.0e-9:
            # Fallback to the mouth-like footprint size when ring radius is missing.
            mouth_r = max(float(rep.get("half_min", 0.0)), float(rep.get("half_max", 0.0)))
        inner_ctx = float(rep.get("inner_context", 0.0))
        sign = None
        best = None
        for layer in sorted(layers, key=lambda l: abs(float(l.get("dt", 0.0)))):
            dt = float(layer.get("dt", 0.0))
            adt = abs(dt)
            if adt < float(X1_CHAMFER_RESOLVED_LAYER_MIN_DT):
                continue
            if adt > float(X1_CHAMFER_RESOLVED_LAYER_MAX_DT):
                continue
            r_max = float(layer.get("r_max", 0.0))
            r_med = float(layer.get("r_med", 0.0))
            if r_max <= 1.0e-9:
                continue
            # Body/seat should be smaller than mouth but not collapse to the core bore.
            if r_max >= mouth_r * 0.995:
                continue
            if inner_ctx > 0.0 and r_max <= inner_ctx * float(X1_CHAMFER_RESOLVED_CORE_CLEARANCE):
                continue
            scale = r_max / max(mouth_r, 1.0e-9)
            if scale < float(X1_CHAMFER_RESOLVED_MIN_SCALE) or scale > float(X1_CHAMFER_RESOLVED_MAX_SCALE):
                continue
            sign = 1.0 if dt >= 0.0 else -1.0
            best = {
                "dt": dt,
                "depth": adt,
                "radius_reference": r_max,
                "radius_med": r_med,
                "mouth_radius": mouth_r,
                "scale": scale,
                "layer": layer,
                "direction_sign": sign,
            }
            break
        if best is None:
            return None
        depth = max(float(X1_CHAMFER_RESOLVED_MIN_DEPTH), min(float(X1_CHAMFER_RESOLVED_MAX_DEPTH), float(best["depth"])))
        best["depth"] = depth
        return best
    except Exception:
        return None


def scaled_form_points_for_layer(desc, scale):
    """Return scaled 3D footprint points around the form center in its local plane."""
    axis_name = desc.get("axis", "Z")
    center = desc.get("center", v_new(0, 0, 0))
    axial = scalar_on_axis(center, axis_name)
    c2 = point_to_2d_for_axis(center, axis_name)
    out = []
    for p in list(desc.get("points3d", [])):
        u, v = point_to_2d_for_axis(p, axis_name)
        su = c2[0] + (float(u) - c2[0]) * float(scale)
        sv = c2[1] + (float(v) - c2[1]) * float(scale)
        out.append(center_from_axis_and_2d(axis_name, axial, su, sv))
    return out


def shape_from_scaled_form(desc, layer_info):
    """Create a diagnostic prism from a scaled footprint and one-way depth."""
    try:
        axis_name = desc.get("axis", "Z")
        axis = axis_vector(axis_name)
        depth = float(layer_info.get("depth", 0.0))
        sign = float(layer_info.get("direction_sign", 1.0))
        scale = float(layer_info.get("scale", 1.0))
        if depth <= 1.0e-9:
            return None
        pts = scaled_form_points_for_layer(desc, scale)
        if len(pts) < 3:
            return None
        # Remove consecutive near-duplicate points; FreeCAD can fail on them.
        cleaned = []
        for p in pts:
            if not cleaned or v_dist(cleaned[-1], p) > 1.0e-7:
                cleaned.append(p)
        if len(cleaned) < 3:
            return None
        if v_dist(cleaned[0], cleaned[-1]) > 1.0e-7:
            cleaned.append(cleaned[0])
        poly = Part.makePolygon(cleaned)
        face = Part.Face(poly)
        return face.extrude(v_scale(axis, sign * depth))
    except Exception:
        return None


def emit_chamfer_resolved_form_marker(doc, group, rep, index, source_obj):
    desc = rep.get("desc")
    if not desc:
        return None
    layer_info = choose_chamfer_resolved_layer(rep)
    if not layer_info:
        return None
    try:
        shape = shape_from_scaled_form(desc, layer_info)
        if shape is None:
            return None
        top_label = str(rep.get("label", "?"))
        axis_name = desc.get("axis", "?")
        obj = doc.addObject("Part::Feature", "X1_R20B_ChamferResolvedForm_%03d" % index)
        obj.Shape = shape
        copied = copy_source_placement_if_needed(obj, source_obj)
        width = float(desc.get("width", 0.0)) * float(layer_info.get("scale", 1.0))
        height = float(desc.get("height", 0.0)) * float(layer_info.get("scale", 1.0))
        obj.Label = "X1 R20B DIAGNOSTIC chamfer-resolved form %03d | %s | axis=%s | seat=%.3f x %.3f | depth=%.3f" % (
            index, top_label, axis_name, width, height, float(layer_info.get("depth", 0.0))
        )
        add_custom_text_property(obj, "X1_DiagnosticOnly", "true")
        add_common_feature_metadata(
            obj,
            family="NONROUND_FORM",
            role="CHAMFER_RESOLVED_BODY",
            stage="CHAMFER_RESOLVED_BODY",
            kind="diagnostic",
            profile=str(top_label),
        )
        add_custom_text_property(obj, "X1_FormType", top_label)
        add_custom_text_property(obj, "X1_FormResolution", "chamfer_resolved_body_layer")
        add_custom_text_property(obj, "X1_Axis", str(axis_name))
        add_custom_text_property(obj, "X1_Center", vec_to_text(desc.get("center", v_new(0, 0, 0))))
        add_custom_text_property(obj, "X1_MouthWidth", "%.6f" % float(desc.get("width", 0.0)))
        add_custom_text_property(obj, "X1_MouthHeight", "%.6f" % float(desc.get("height", 0.0)))
        add_size_pair_metadata(obj, "X1_MouthSize", float(desc.get("width", 0.0)), float(desc.get("height", 0.0)))
        add_custom_text_property(obj, "X1_ResolvedWidth", "%.6f" % width)
        add_custom_text_property(obj, "X1_ResolvedHeight", "%.6f" % height)
        add_size_pair_metadata(obj, "X1_ResolvedSize", width, height)
        add_custom_text_property(obj, "X1_ResolvedDepth", "%.6f" % float(layer_info.get("depth", 0.0)))
        add_custom_text_property(obj, "X1_ChamferScale", "%.6f" % float(layer_info.get("scale", 0.0)))
        add_custom_text_property(obj, "X1_ResolvedScale", "%.6f" % float(layer_info.get("scale", 0.0)))
        add_custom_text_property(obj, "X1_MouthLayerRadius", "%.6f" % float(layer_info.get("mouth_radius", 0.0)))
        add_custom_text_property(obj, "X1_ResolvedLayerRadius", "%.6f" % float(layer_info.get("radius_reference", 0.0)))
        add_custom_text_property(obj, "X1_ResolvedLayerDt", "%.6f" % float(layer_info.get("dt", 0.0)))
        add_custom_text_property(obj, "X1_ContextOuterRadius", "%.6f" % float(rep.get("outer_context", 0.0)))
        add_custom_text_property(obj, "X1_ContextInnerRadius", "%.6f" % float(rep.get("inner_context", 0.0)))
        add_custom_text_property(obj, "X1_ChamferStatus", str(rep.get("status", "?")))
        add_custom_text_property(obj, "X1_MouthLikeOuter", str(bool(rep.get("mouth_like_outer", False))))
        add_custom_text_property(obj, "X1_CoreSmaller", str(bool(rep.get("core_smaller", False))))
        add_custom_text_property(obj, "X1_ChamferAngles", ",".join("%.3f" % float(a) for a in list(rep.get("chamfer_angles", []))[:8]))
        add_custom_text_property(obj, "X1_Source", str(rep.get("source", desc.get("source", "?"))))
        try:
            obj.ViewObject.ShapeColor = (1.0, 0.25, 0.0)
            obj.ViewObject.Transparency = int(X1_CHAMFER_RESOLVED_FORM_MARKER_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_to_group(group, obj)
        x1_msg("  X1 R20B chamfer-resolved form marker %03d: %s axis=%s color=(1.0, 0.25, 0.0) mouth_size=(%.3f x %.3f) resolved_size=(%.3f x %.3f) depth=%.3f scale=%.3f mouth_r=%.3f layer_r=%.3f layer_dt=%+.3f placement_copied=%s source=%s" % (
            index,
            top_label,
            axis_name,
            float(desc.get("width", 0.0)),
            float(desc.get("height", 0.0)),
            width,
            height,
            float(layer_info.get("depth", 0.0)),
            float(layer_info.get("scale", 0.0)),
            float(layer_info.get("mouth_radius", 0.0)),
            float(layer_info.get("radius_reference", 0.0)),
            float(layer_info.get("dt", 0.0)),
            str(copied),
            compact_source_name(rep.get("source", desc.get("source", "?"))),
        ))
        return obj
    except Exception as exc:
        x1_warn("  X1 R20B chamfer-resolved form marker %03d skipped after error: %s" % (index, exc))
        return None


def emit_chamfer_resolved_form_markers(doc, parent_group, chamfer_reports, source_obj):
    if not X1_EMIT_CHAMFER_RESOLVED_FORM_MARKERS or not chamfer_reports:
        return 0
    # R18G: parent_group is already the semantic "Chamfer-Resolved Seats"
    # feature-family group created by build_feature_tree_groups().
    marker_group = parent_group
    count = 0
    for rep in chamfer_reports:
        if count >= int(X1_MAX_CHAMFER_RESOLVED_FORM_MARKERS):
            break
        marker = emit_chamfer_resolved_form_marker(doc, marker_group, rep, count + 1, source_obj)
        if marker is not None:
            count += 1
    x1_msg("  R20B chamfer-resolved form diagnostic markers: emitted %d" % count)
    if count:
        x1_msg("  R20B structured feature tree: bores, anchored pockets, hex/nut mouth diagnostics, chamfer-resolved seats, and rejected/debug diagnostics are separated")
    return count

# =============================================================================
# Main processing
# =============================================================================


def process_object(doc, output_group, obj, obj_index):
    label = getattr(obj, "Label", getattr(obj, "Name", "Object"))
    try:
        shape = obj.Shape
    except Exception:
        x1_warn("Skipping %s: no Shape" % label)
        return {"observations": 0, "accepted": 0, "emitted": 0, "rejected": 0}

    log = []
    bb = None
    try:
        bb = shape.BoundBox
    except Exception:
        pass

    observations = collect_observations(shape, label, log)
    primitives, rejected = build_primitives(observations, bb)
    fused = fuse_primitives(primitives)
    stack_infos = annotate_stepped_relations(fused)
    usage = observation_usage_report(observations, fused)

    # Keep output folder structure: one subfolder per source object.
    obj_group = ensure_group(doc, "X1_R20B_%03d_%s" % (obj_index, str(getattr(obj, "Name", "Object"))[:40]))
    add_to_group(output_group, obj_group)

    # R20B structured feature tree.  Detection stays R18A-equivalent; only the
    # emitted objects are routed into clearer subgroups for later FAR Mesh use.
    feature_groups = build_feature_tree_groups(doc, obj_group)
    accepted_bores_group = feature_groups.get("accepted_bores") or obj_group
    anchored_pockets_group = feature_groups.get("anchored_circular_pockets") or obj_group
    mouth_forms_group = feature_groups.get("hex_nut_mouth_diagnostics") or obj_group
    resolved_seats_group = feature_groups.get("hex_nut_chamfer_resolved_seats") or obj_group
    fast_diagnostics_group = feature_groups.get("fast_tessellation_diagnostics") or obj_group
    reconciliation_group = feature_groups.get("chamfer_aware_reconciliation") or obj_group
    tessellated_probe_group = feature_groups.get("tessellated_axis_side_probe") or obj_group
    consolidated_ledger_group = feature_groups.get("consolidated_tessellated_ledger") or obj_group
    rejected_diagnostics_group = feature_groups.get("rejected_diagnostics") or obj_group

    emitted = 0
    for i, prim in enumerate(fused, start=1):
        if emit_cylinder(doc, accepted_bores_group, prim, i, obj) is not None:
            emitted += 1
            if X1_CREATE_DEBUG_RINGS:
                for oi, obs in enumerate(prim.get("observations", []), start=1):
                    if obs.get("kind") == "ring":
                        emit_ring_point(doc, accepted_bores_group, obs, i * 1000 + oi, True)

    if X1_CREATE_REJECTED_POINTS:
        ri = 1
        for group, reason in rejected:
            for obs in group.get("observations", []):
                if obs.get("kind") == "ring":
                    emit_ring_point(doc, rejected_diagnostics_group, obs, ri, False)
                    ri += 1

    # Source breakdown helps us see why a part is failing.
    analytic_cyls = sum(1 for o in observations if o["kind"] == "cylinder_face")
    analytic_rings = sum(1 for o in observations if o.get("is_analytic"))
    inner_rings = sum(1 for o in observations if o.get("is_inner_wire"))
    weak_wires = sum(1 for o in observations if o["kind"] == "ring" and not o.get("is_analytic") and not o.get("is_inner_wire"))

    x1_msg("X1 R20B object: %s" % label)
    x1_msg("  observations: %d (cylinder_faces=%d, analytic_rings=%d, inner_wires=%d, weak_closed_wires=%d)" % (
        len(observations), analytic_cyls, analytic_rings, inner_rings, weak_wires
    ))
    x1_msg("  candidate groups: %d" % (len(primitives) + len(rejected)))
    x1_msg("  accepted primitives before fusion: %d" % len(primitives))
    x1_msg("  accepted primitives after fusion: %d" % len(fused))
    x1_msg("  emitted cylinders: %d" % emitted)
    if X1_PRINT_ACCEPTED_BREAKDOWN:
        axes, profiles = primitive_breakdown(fused)
        x1_msg("  accepted by axis: X=%d, Y=%d, Z=%d, FREE=%d" % (axes.get("X", 0), axes.get("Y", 0), axes.get("Z", 0), axes.get("FREE", 0)))
        if profiles:
            profile_parts = ["%s=%d" % (k, profiles[k]) for k in sorted(profiles.keys())]
            x1_msg("  accepted by profile: %s" % "; ".join(profile_parts))
        x1_msg("  evidence used: inner_wires=%d/%d, weak_closed_wires=%d/%d, analytic=%d/%d, cylinder_faces=%d/%d" % (
            usage.get("inner_used", 0), usage.get("inner_total", 0),
            usage.get("weak_used", 0), usage.get("weak_total", 0),
            usage.get("analytic_used", 0), usage.get("analytic_total", 0),
            usage.get("cyl_used", 0), usage.get("cyl_total", 0),
        ))
        if stack_infos:
            x1_msg("  stepped/counterbore-like stacks: %d" % len(stack_infos))
            for info in stack_infos[:8]:
                x1_msg("    stack %02d: axis=%s segments=%d radius %.3f -> %.3f" % (
                    info.get("id", 0), info.get("axis", "?"), info.get("segments", 0), info.get("max_radius", 0.0), info.get("min_radius", 0.0)
                ))
        else:
            x1_msg("  stepped/counterbore-like stacks: 0")
    x1_msg("  rejected groups: %d" % len(rejected))
    pocket_info = print_missing_pocket_diagnostics(rejected, bb, fused)
    pocket_regions = []
    try:
        pocket_regions = pocket_info.get("regions", [])
    except Exception:
        pocket_regions = []
    pocket_marker_count = emit_strong_pocket_region_markers(doc, anchored_pockets_group, pocket_regions, obj, bb, fused)

    # R20B: inspect additional feature forms such as hex nut pockets and elongated slots.
    # Diagnostic-only: no geometry is emitted and the stable bore/pocket path is untouched.
    form_candidates = print_nonround_form_diagnostics(shape, label, bb)
    form_marker_count = emit_nonround_form_markers(doc, mouth_forms_group, form_candidates, obj)
    chamfer_reports = print_form_chamfer_diagnostics(form_candidates, observations, fused)
    resolved_form_marker_count = emit_chamfer_resolved_form_markers(doc, resolved_seats_group, chamfer_reports, obj)

    # R20B: diagnostic-only FAST tessellation/chamfer evidence from R18F.
    # This does not modify accepted bores, anchored pockets, form mouth markers,
    # chamfer-resolved seats, or rejection rules from the R18B/R18A path.
    fast_diag = x1_r20b_emit_fast_chamfer_tolerant_diagnostics(doc, fast_diagnostics_group, obj, obj_index)

    # R20B: reconcile FAST layer stacks with the conservative accepted/rejected path.
    # This is diagnostic-only. It classifies likely chamfer-mouth-sized layers
    # separately from body/core-sized layer evidence so oversized chamfer mouths are
    # not mistaken for true bore cylinders.
    reconciliation = emit_chamfer_aware_reconciliation_markers(
        doc, reconciliation_group, fused, rejected, fast_diag.get("stacks", []), obj, bb
    )

    # R20B: diagnostic-only multi-system tessellated reader for hard imported meshes.
    # This scans from all six axis sides and pairs side evidence without touching
    # the accepted R18B/R18A bore path or the R18F/R20B evidence ledger.
    side_probe = emit_tessellated_axis_side_probe_markers(
        doc, tessellated_probe_group, obj, obj_index, fused, bb
    )

    # R20B: object-local consolidated ledger.  It reads the already-created
    # FAST stack evidence and side-scan evidence, merges duplicate physical
    # candidates, suppresses weak single-side noise near accepted bores, and
    # keeps everything diagnostic-only.
    consolidated_ledger = emit_r20b_consolidated_tessellated_ledger(
        doc, consolidated_ledger_group, fused, rejected, fast_diag.get("stacks", []), side_probe, obj, bb, accepted_bores_group
    )

    if X1_PRINT_REJECTED_SUMMARY and rejected:
        shown = 0
        for group, reason in rejected:
            if shown >= X1_MAX_REJECTED_LINES:
                remaining = len(rejected) - shown
                if remaining > 0:
                    x1_msg("    ... %d more rejected groups" % remaining)
                break
            robs = group.get("observations", [])
            rr = median([o.get("radius", 0.0) for o in robs]) if robs else 0.0
            ax = axis_hint(group.get("axis", axis_vector("Z")))
            sources = sorted(set(compact_source_name(o.get("source", "?")) for o in robs))
            x1_msg("    rejected %02d: axis=%s r=%.3f obs=%d reason=%s sources=%s" % (
                shown + 1, ax, rr, len(robs), str(reason), ",".join(sources[:3])
            ))
            shown += 1

    for level, message in log[:8]:
        if level == "warning":
            x1_warn(message)
        else:
            x1_msg(message)

    return {
        "observations": len(observations),
        "accepted": len(fused) + int(consolidated_ledger.get("accepted_path_promotions", 0)),
        "emitted": emitted + int(consolidated_ledger.get("accepted_path_promotions", 0)),
        "rejected": len(rejected),
        "pocket_markers": pocket_marker_count,
        "forms": len(form_candidates),
        "form_markers": form_marker_count,
        "chamfer_reports": len(chamfer_reports),
        "resolved_form_markers": resolved_form_marker_count,
        "fast_observations": int(fast_diag.get("observations", 0)),
        "fast_e074_markers": int(fast_diag.get("e074_markers", 0)),
        "fast_stack_markers": int(fast_diag.get("stack_markers", 0)),
        "fast_weak_markers": int(fast_diag.get("weak_markers", 0)),
        "fast_suspect_markers": int(fast_diag.get("suspect_markers", 0)),
        "fast_markers": int(fast_diag.get("markers", 0)),
        "reconciliation_markers": int(reconciliation.get("markers", 0)),
        "reconciliation_chamfer_mouth_markers": int(reconciliation.get("chamfer_mouth_markers", 0)),
        "reconciliation_body_candidate_markers": int(reconciliation.get("body_candidate_markers", 0)),
        "reconciliation_missing_candidate_markers": int(reconciliation.get("missing_candidate_markers", 0)),
        "reconciliation_covered_markers": int(reconciliation.get("covered_markers", 0)),
        "reconciliation_accepted_mouth_markers": int(reconciliation.get("accepted_mouth_markers", 0)),
        "reconciliation_paired_missing_bore_chamfer_markers": int(reconciliation.get("paired_missing_bore_chamfer_markers", 0)),
        "reconciliation_tessellation_only_markers": int(reconciliation.get("tessellation_only_markers", 0)),
        "reconciliation_ledger_entries": int(reconciliation.get("ledger_entries", 0)),
        "side_probe_candidates": int(side_probe.get("candidates", 0)),
        "side_probe_pairs": int(side_probe.get("pairs", 0)),
        "side_probe_pair_markers": int(side_probe.get("pair_markers", 0)),
        "side_probe_single_markers": int(side_probe.get("single_markers", 0)),
        "side_probe_already_covered": int(side_probe.get("already_covered", 0)),
        "side_probe_new_candidates": int(side_probe.get("new_candidates", 0)),
        "consolidated_entries": int(consolidated_ledger.get("entries", 0)),
        "consolidated_markers": int(consolidated_ledger.get("markers", 0)),
        "consolidated_stable_covered": int(consolidated_ledger.get("stable_covered", 0)),
        "consolidated_chamfer_body": int(consolidated_ledger.get("chamfer_body", 0)),
        "consolidated_missing": int(consolidated_ledger.get("missing", 0)),
        "consolidated_tessellated": int(consolidated_ledger.get("tessellated", 0)),
        "consolidated_suppressed": int(consolidated_ledger.get("suppressed", 0)),
        "tessellated_review_markers": int(consolidated_ledger.get("review_markers", 0)),
        "tessellated_review_markers_tier_a": int(consolidated_ledger.get("review_markers_tier_a", 0)),
        "tessellated_review_markers_tier_b": int(consolidated_ledger.get("review_markers_tier_b", 0)),
        "promotion_preview_cylinders": int(consolidated_ledger.get("promotion_preview", 0)),
        "accepted_path_promotions": int(consolidated_ledger.get("accepted_path_promotions", 0)),
    }


def main():
    if App is None or Gui is None or Part is None:
        x1_err("This macro must be run inside FreeCAD.")
        return

    doc = App.ActiveDocument
    if doc is None:
        x1_err("No active FreeCAD document.")
        return

    try:
        selected = list(Gui.Selection.getSelection())
    except Exception:
        selected = []
    if not selected:
        x1_err("No selected object. Select one or more objects with a Shape first.")
        return

    x1_msg("")
    x1_msg("=== %s bore feature recognition started ===" % X1_VERSION)
    x1_msg("Selected objects: %d" % len(selected))
    x1_msg("Mode: R5-stable wire/inner-wire evidence first; R20B adds guarded accepted promotion only for confirmed missing bore/chamfer ledger entries")
    x1_msg("R20B policy: accepted-feature path can now promote only guarded missing-bore-with-chamfer entries confirmed by FAST stack + side-pair evidence; Tier A/B review markers remain diagnostic")
    x1_msg("Axis colors: X=red, Y=green, Z=blue, FREE=yellow")

    output_group = ensure_group(doc, X1_OUTPUT_GROUP_NAME)

    try:
        X1_R20B_STRUCTURED_LEDGER_ROWS[:] = []
    except Exception:
        pass

    total_obs = 0
    total_acc = 0
    total_emit = 0
    total_rej = 0
    total_pocket_markers = 0
    total_forms = 0
    total_form_markers = 0
    total_chamfer_reports = 0
    total_resolved_form_markers = 0
    total_fast_observations = 0
    total_fast_e074_markers = 0
    total_fast_stack_markers = 0
    total_fast_weak_markers = 0
    total_fast_suspect_markers = 0
    total_fast_markers = 0
    total_reconciliation_markers = 0
    total_reconciliation_chamfer_mouth_markers = 0
    total_reconciliation_body_candidate_markers = 0
    total_reconciliation_missing_candidate_markers = 0
    total_reconciliation_covered_markers = 0
    total_reconciliation_accepted_mouth_markers = 0
    total_reconciliation_paired_missing_bore_chamfer_markers = 0
    total_reconciliation_tessellation_only_markers = 0
    total_reconciliation_ledger_entries = 0
    total_side_probe_candidates = 0
    total_side_probe_pairs = 0
    total_side_probe_pair_markers = 0
    total_side_probe_single_markers = 0
    total_side_probe_already_covered = 0
    total_side_probe_new_candidates = 0
    total_consolidated_entries = 0
    total_consolidated_markers = 0
    total_consolidated_stable_covered = 0
    total_consolidated_chamfer_body = 0
    total_consolidated_missing = 0
    total_consolidated_tessellated = 0
    total_consolidated_suppressed = 0
    total_tessellated_review_markers = 0
    total_tessellated_review_markers_tier_a = 0
    total_tessellated_review_markers_tier_b = 0
    total_promotion_preview_cylinders = 0
    total_accepted_path_promotions = 0
    for i, obj in enumerate(selected, start=1):
        try:
            result = process_object(doc, output_group, obj, i)
            total_obs += result["observations"]
            total_acc += result["accepted"]
            total_emit += result["emitted"]
            total_rej += result["rejected"]
            total_pocket_markers += result.get("pocket_markers", 0)
            total_forms += result.get("forms", 0)
            total_form_markers += result.get("form_markers", 0)
            total_chamfer_reports += result.get("chamfer_reports", 0)
            total_resolved_form_markers += result.get("resolved_form_markers", 0)
            total_fast_observations += result.get("fast_observations", 0)
            total_fast_e074_markers += result.get("fast_e074_markers", 0)
            total_fast_stack_markers += result.get("fast_stack_markers", 0)
            total_fast_weak_markers += result.get("fast_weak_markers", 0)
            total_fast_suspect_markers += result.get("fast_suspect_markers", 0)
            total_fast_markers += result.get("fast_markers", 0)
            total_reconciliation_markers += result.get("reconciliation_markers", 0)
            total_reconciliation_chamfer_mouth_markers += result.get("reconciliation_chamfer_mouth_markers", 0)
            total_reconciliation_body_candidate_markers += result.get("reconciliation_body_candidate_markers", 0)
            total_reconciliation_missing_candidate_markers += result.get("reconciliation_missing_candidate_markers", 0)
            total_reconciliation_covered_markers += result.get("reconciliation_covered_markers", 0)
            total_reconciliation_accepted_mouth_markers += result.get("reconciliation_accepted_mouth_markers", 0)
            total_reconciliation_paired_missing_bore_chamfer_markers += result.get("reconciliation_paired_missing_bore_chamfer_markers", 0)
            total_reconciliation_tessellation_only_markers += result.get("reconciliation_tessellation_only_markers", 0)
            total_reconciliation_ledger_entries += result.get("reconciliation_ledger_entries", 0)
            total_side_probe_candidates += result.get("side_probe_candidates", 0)
            total_side_probe_pairs += result.get("side_probe_pairs", 0)
            total_side_probe_pair_markers += result.get("side_probe_pair_markers", 0)
            total_side_probe_single_markers += result.get("side_probe_single_markers", 0)
            total_side_probe_already_covered += result.get("side_probe_already_covered", 0)
            total_side_probe_new_candidates += result.get("side_probe_new_candidates", 0)
            total_consolidated_entries += result.get("consolidated_entries", 0)
            total_consolidated_markers += result.get("consolidated_markers", 0)
            total_consolidated_stable_covered += result.get("consolidated_stable_covered", 0)
            total_consolidated_chamfer_body += result.get("consolidated_chamfer_body", 0)
            total_consolidated_missing += result.get("consolidated_missing", 0)
            total_consolidated_tessellated += result.get("consolidated_tessellated", 0)
            total_consolidated_suppressed += result.get("consolidated_suppressed", 0)
            total_tessellated_review_markers += result.get("tessellated_review_markers", 0)
            total_tessellated_review_markers_tier_a += result.get("tessellated_review_markers_tier_a", 0)
            total_tessellated_review_markers_tier_b += result.get("tessellated_review_markers_tier_b", 0)
            total_promotion_preview_cylinders += result.get("promotion_preview_cylinders", 0)
            total_accepted_path_promotions += result.get("accepted_path_promotions", 0)
        except Exception as exc:
            x1_err("Failed object %s: %s" % (getattr(obj, "Label", getattr(obj, "Name", "?")), exc))
            x1_err(traceback.format_exc())

    try:
        doc.recompute()
    except Exception:
        pass

    x1_msg("=== %s finished ===" % X1_VERSION)
    x1_msg("Total observations: %d" % total_obs)
    x1_msg("Total accepted primitives: %d" % total_acc)
    x1_msg("Total emitted cylinders: %d" % total_emit)
    x1_msg("Total rejected groups: %d" % total_rej)
    x1_msg("Total diagnostic pocket-region markers: %d" % total_pocket_markers)
    x1_msg("Total non-round form diagnostic candidates: %d" % total_forms)
    x1_msg("Total non-round form diagnostic markers: %d" % total_form_markers)
    x1_msg("Total chamfer/fase diagnostic reports: %d" % total_chamfer_reports)
    x1_msg("Total chamfer-resolved form diagnostic markers: %d" % total_resolved_form_markers)
    x1_msg("Total R18F FAST observations: %d" % total_fast_observations)
    x1_msg("Total R18F FAST e074 loop-circle markers: %d" % total_fast_e074_markers)
    x1_msg("Total R18F FAST one-ring/layer stack markers: %d" % total_fast_stack_markers)
    x1_msg("Total R18F FAST weak tessellation cluster markers: %d" % total_fast_weak_markers)
    x1_msg("Total R18F FAST suspect one-ring markers: %d" % total_fast_suspect_markers)
    x1_msg("Total R18F FAST diagnostic markers: %d" % total_fast_markers)
    x1_msg("Total R20B reconciliation markers: %d" % total_reconciliation_markers)
    x1_msg("Total R20B chamfer-mouth/transition markers: %d" % total_reconciliation_chamfer_mouth_markers)
    x1_msg("Total R20B body/core candidate markers: %d" % total_reconciliation_body_candidate_markers)
    x1_msg("Total R20B missing-feature candidate markers: %d" % total_reconciliation_missing_candidate_markers)
    x1_msg("Total R20B already-covered markers: %d" % total_reconciliation_covered_markers)
    x1_msg("Total R20B accepted-bore-may-be-mouth markers: %d" % total_reconciliation_accepted_mouth_markers)
    x1_msg("Total R20B paired missing bore/chamfer markers: %d" % total_reconciliation_paired_missing_bore_chamfer_markers)
    x1_msg("Total R20B tessellation-only unanchored markers: %d" % total_reconciliation_tessellation_only_markers)
    x1_msg("Total R20B evidence-ledger entries: %d" % total_reconciliation_ledger_entries)
    x1_msg("Total R20B tessellated axis-side candidates: %d" % total_side_probe_candidates)
    x1_msg("Total R20B tessellated paired candidates: %d" % total_side_probe_pairs)
    x1_msg("Total R20B tessellated pair markers: %d" % total_side_probe_pair_markers)
    x1_msg("Total R20B tessellated single-side markers: %d" % total_side_probe_single_markers)
    x1_msg("Total R20B tessellated already-covered candidates: %d" % total_side_probe_already_covered)
    x1_msg("Total R20B tessellated new diagnostic candidates: %d" % total_side_probe_new_candidates)
    x1_msg("Total R20B consolidated ledger entries: %d" % total_consolidated_entries)
    x1_msg("Total R20B consolidated ledger markers: %d" % total_consolidated_markers)
    x1_msg("Total R20B consolidated stable-covered entries: %d" % total_consolidated_stable_covered)
    x1_msg("Total R20B consolidated chamfer/body entries: %d" % total_consolidated_chamfer_body)
    x1_msg("Total R20B consolidated missing-feature entries: %d" % total_consolidated_missing)
    x1_msg("Total R20B consolidated tessellated entries: %d" % total_consolidated_tessellated)
    x1_msg("Total R20B consolidated suppressed entries: %d" % total_consolidated_suppressed)
    x1_msg("Total R20B tessellated review markers: %d" % total_tessellated_review_markers)
    x1_msg("Total R20B tessellated review Tier A markers: %d" % total_tessellated_review_markers_tier_a)
    x1_msg("Total R20B tessellated review Tier B markers: %d" % total_tessellated_review_markers_tier_b)
    x1_msg("Total R20B promotion-preview cylinders: %d" % total_promotion_preview_cylinders)
    x1_msg("Total R20B accepted-path promotions: %d" % total_accepted_path_promotions)
    x1_msg("Total R20B structured export rows: %d" % len(X1_R20B_STRUCTURED_LEDGER_ROWS))
    r20b_write_structured_ledger_exports(doc)
    x1_msg("Output group: %s" % X1_OUTPUT_GROUP_NAME)



# =============================================================================
# Embedded R18F FAST chamfer-tolerant diagnostic code
# Source: x1_2026_r18f_fast_chamfer_tolerant_diagnostics.fcmacro
# Integrated into R20B without changing the accepted R18B/R18A path.
# =============================================================================

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X1_2026_R18F_FAST_chamfer_tolerant_diagnostics.FCMacro

Chamfer-tolerant guarded fast diagnostic-only companion for X1_2026_R18B_structured_feature_tree.

R18F changes over R18E FAST:
- face scans are distributed across the whole face list instead of only the first cap;
- medium tessellated objects get a selective closed-edge fallback instead of skipping;
- large objects get an evenly sampled edge fallback, still bounded and diagnostic-only.

Why this version exists
-----------------------
The first R18C diagnostic macro was too broad: it combined dense E074/PCA circle
checks, one-ring grouping, weak tessellation clustering, and g060-style edge
proposal scans in one pass. On tessellated parts this can freeze the FreeCAD GUI
because the macro runs on the GUI thread.

This FAST version is deliberately bounded:
- R18B accepted-feature detection is NOT changed.
- No accepted features are promoted here.
- g060 broad edge proposals are disabled by default.
- Marker output uses lightweight rings, not many solid cylinders.
- Loop/edge samples are capped.
- A soft time budget stops safely with partial diagnostics instead of hanging.
- Gui.updateGui() is called during long loops so the GUI has chances to repaint.

Output group
------------
X1_2026_R18F_FAST_Chamfer_Tolerant_Diagnostics

Diagnostic groups
-----------------
- Fast_E074_Loop_Circles: now emitted only when tied to guarded stacks
- Fast_One_Ring_Layer_Stacks: radius/evidence guarded, with explicit chamfer/stepped-stack tolerance
- Fast_Weak_Tessellation_Clusters: console candidates, markers only for anchored clusters
- Fast_Suspect_One_Ring_Circles: console candidates, marker emission disabled by default
- Skipped_Heavy_G060_Disabled

Tune only at the constants below. Defaults are intentionally conservative.
"""

import math
import time
from collections import defaultdict

import FreeCAD as App
import FreeCADGui as Gui
import Part

try:
    import numpy as np
except Exception:
    np = None

R20B_FAST_VERSION = "X1_2026_R18F_FAST_chamfer_tolerant_diagnostics_embedded"
VERSION = R20B_FAST_VERSION

# -----------------------------------------------------------------------------
# Performance / safety limits
# -----------------------------------------------------------------------------
TIME_BUDGET_SECONDS = 75.0       # graceful partial stop instead of GUI freeze
MAX_FACES_PER_OBJECT = 4500      # distributed face-wire pass cap, not first-N only
MAX_WIRES_PER_OBJECT = 6500      # wire pass cap
MAX_EDGES_FALLBACK = 5200        # selective closed-edge fallback cap
MAX_POINTS_PER_LOOP = 180        # downsample a sampled wire/edge to this size
SAMPLES_PER_WIRE_EDGE = 3        # low-cost sampling for face wires
SAMPLES_PER_CLOSED_EDGE = 16     # closed edge needs more points than face wire
GUI_PULSE_EVERY = 100            # call Gui.updateGui every N processed items

# Marker caps. Keep low: diagnostic visibility without document bloat.
MAX_E074_MARKERS = 36
MAX_STACK_MARKERS = 36
MAX_WEAK_CLUSTER_MARKERS = 36
MAX_SUSPECT_MARKERS = 36

# g060 is intentionally off because it was the most likely expensive layer.
# Turn on only after FAST diagnostics prove useful and the selected object is small.
ENABLE_G060_EDGE_PROPOSALS = False
MAX_G060_EDGES_IF_ENABLED = 350
MAX_G060_MARKERS = 20

# Geometry thresholds, intentionally relative/broad rather than part-specific.
MIN_RADIUS = 0.45
MAX_RADIUS_ABSOLUTE = 180.0
MIN_POINTS = 10
MAX_REL_SPREAD_CIRCLE = 0.12      # circle/ring acceptance for diagnostics
MAX_REL_SPREAD_SUSPECT = 0.22     # loose candidate collection only; not enough for drawing

# R18F marker guards: keep console diagnostics broad, but draw only anchored evidence.
# This prevents the many false-positive diagnostic circles seen in R18D while
# preserving the useful distributed scan, chamfer/stepped-stack evidence, and observation counts.
EMIT_UNANCHORED_SUSPECT_MARKERS = False
MIN_STACK_E074_CONFIRMED = 1
MIN_STACK_INNER_MEMBERS = 2
MAX_MARKER_RADIUS_FRACTION_OF_BBOX = 0.18
MAX_STACK_RADIUS_RANGE_RATIO = 0.55

# Chamfer/step tolerance: R18E correctly suppressed noisy one-ring circles,
# but it also suppressed real chamfer stacks where the same centerline has
# multiple reliable E074 rings with intentionally changing radius. Keep this
# stricter than the old broad R18D behavior: require 3+ layers and 2+ E074
# confirmations, and still reject giant/silhouette stacks by radius fraction.
MIN_CHAMFER_STACK_MEMBERS = 3
MIN_CHAMFER_STACK_E074_CONFIRMED = 2
MIN_CHAMFER_STACK_RADIUS_DELTA_RATIO = 0.18
MAX_CHAMFER_STACK_RADIUS_RANGE_RATIO = 1.15

MIN_WEAK_CLUSTER_E074_CONFIRMED = 2
MIN_WEAK_CLUSTER_MEMBERS = 2
MAX_WEAK_CLUSTER_RADIUS_RANGE_RATIO = 0.18

CENTER_GRID = 2.5
STACK_MIN_AXIAL_SPAN = 0.75
STACK_RADIUS_RATIO_MAX = 2.25
WEAK_CLUSTER_GRID = 4.0

AXIS_VECTORS = {
    "X": App.Vector(1, 0, 0),
    "Y": App.Vector(0, 1, 0),
    "Z": App.Vector(0, 0, 1),
}

COLORS = {
    "e074": (0.0, 0.80, 1.0),       # cyan
    "stack": (0.65, 0.25, 1.0),     # violet
    "weak": (1.0, 0.85, 0.0),       # yellow
    "suspect": (1.0, 0.45, 0.15),   # orange
    "disabled": (0.55, 0.55, 0.55),
}


# -----------------------------------------------------------------------------
# Console / utility helpers
# -----------------------------------------------------------------------------
def msg(text):
    App.Console.PrintMessage(str(text) + "\n")


def warn(text):
    App.Console.PrintWarning(str(text) + "\n")


def err(text):
    App.Console.PrintError(str(text) + "\n")


def pulse_gui():
    try:
        Gui.updateGui()
    except Exception:
        pass


def safe_name(text):
    out = []
    for ch in str(text):
        if ch.isalnum() or ch in "_-.":
            out.append(ch)
        else:
            out.append("_")
    return ("".join(out) or "unnamed")[:90]


def add_group(doc, parent, label):
    group = doc.addObject("App::DocumentObjectGroup", safe_name(label))
    group.Label = label
    if parent is not None:
        try:
            parent.addObject(group)
        except Exception:
            pass
    return group


def add_prop(obj, prop_type, name, value):
    try:
        if not hasattr(obj, name):
            obj.addProperty(prop_type, name, "X1", name)
        setattr(obj, name, value)
    except Exception:
        pass


def axis_coord(p, axis):
    if axis == "X":
        return float(p.x)
    if axis == "Y":
        return float(p.y)
    return float(p.z)


def cross_coords(p, axis):
    if axis == "X":
        return (float(p.y), float(p.z))
    if axis == "Y":
        return (float(p.x), float(p.z))
    return (float(p.x), float(p.y))


def point_from_cross_axis(cross, axial, axis):
    if axis == "X":
        return App.Vector(float(axial), float(cross[0]), float(cross[1]))
    if axis == "Y":
        return App.Vector(float(cross[0]), float(axial), float(cross[1]))
    return App.Vector(float(cross[0]), float(cross[1]), float(axial))


def downsample(points, limit=MAX_POINTS_PER_LOOP):
    if len(points) <= limit:
        return points
    if limit <= 2:
        return [points[0], points[-1]]
    step = (len(points) - 1) / float(limit - 1)
    return [points[int(round(i * step))] for i in range(limit)]


def select_evenly(items, limit):
    """Return up to limit items spread across the full list, preserving order.

    R18C processed the first N faces only. That missed evidence on high-face-count
    tessellated parts when useful wires were later in the face list. R18F keeps the
    same bounded cost but samples across the complete object.
    """
    items = list(items)
    n = len(items)
    if n <= limit:
        return items, False
    if limit <= 1:
        return [items[0]], True
    step = (n - 1) / float(limit - 1)
    picked = []
    used = set()
    for i in range(limit):
        idx = int(round(i * step))
        if idx not in used:
            used.add(idx)
            picked.append(items[idx])
    return picked, True


def edge_length(edge):
    try:
        return float(edge.Length)
    except Exception:
        return 0.0


def sample_edge(edge, count):
    pts = []
    try:
        first = float(edge.FirstParameter)
        last = float(edge.LastParameter)
        if abs(last - first) < 1e-12:
            return [edge.CenterOfMass]
        n = max(2, int(count))
        for i in range(n):
            t = i / float(n - 1)
            pts.append(edge.valueAt(first + t * (last - first)))
    except Exception:
        try:
            pts.append(edge.CenterOfMass)
        except Exception:
            pass
    return pts


def sample_wire(wire, samples_per_edge=SAMPLES_PER_WIRE_EDGE):
    pts = []
    try:
        for edge_index, edge in enumerate(wire.Edges):
            edge_pts = sample_edge(edge, samples_per_edge)
            if pts and edge_pts:
                pts.extend(edge_pts[1:])
            else:
                pts.extend(edge_pts)
            if len(pts) >= MAX_POINTS_PER_LOOP * 2:
                break
    except Exception:
        pass
    return downsample(pts, MAX_POINTS_PER_LOOP)


def edge_may_be_closed(edge):
    try:
        if edge_length(edge) < 0.25:
            return False
        p0 = edge.valueAt(edge.FirstParameter)
        p1 = edge.valueAt(edge.LastParameter)
        return p0.distanceToPoint(p1) <= max(0.05, edge.Length * 0.015)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Circle fits
# -----------------------------------------------------------------------------
def circle_fit_2d(points_2d):
    if np is None or len(points_2d) < MIN_POINTS:
        return None
    try:
        arr = np.asarray(points_2d, dtype=float)
        x = arr[:, 0]
        y = arr[:, 1]
        xm = float(np.mean(x))
        ym = float(np.mean(y))
        u = x - xm
        v = y - ym
        suu = float(np.sum(u * u))
        svv = float(np.sum(v * v))
        suv = float(np.sum(u * v))
        suuu = float(np.sum(u * u * u))
        svvv = float(np.sum(v * v * v))
        suvv = float(np.sum(u * v * v))
        svuu = float(np.sum(v * u * u))
        A = np.asarray([[suu, suv], [suv, svv]], dtype=float)
        B = np.asarray([0.5 * (suuu + suvv), 0.5 * (svvv + svuu)], dtype=float)
        try:
            uc, vc = np.linalg.solve(A, B)
            cx = float(uc + xm)
            cy = float(vc + ym)
        except Exception:
            cx, cy = xm, ym
        radii = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        radius = float(np.median(radii))
        if radius <= 1e-9:
            return None
        rms = float(np.sqrt(np.mean((radii - radius) ** 2)))
        rel_spread = rms / max(radius, 1e-9)
        return {
            "center_2d": (cx, cy),
            "radius": radius,
            "rms": rms,
            "rel_spread": rel_spread,
            "point_count": int(len(points_2d)),
            "confidence": max(0.0, min(1.0, 1.0 - rel_spread * 8.0)),
        }
    except Exception:
        return None


def axis_circle_fit(points, axis):
    if len(points) < MIN_POINTS:
        return None
    if axis == "X":
        pts2 = [(p.y, p.z) for p in points]
    elif axis == "Y":
        pts2 = [(p.x, p.z) for p in points]
    else:
        pts2 = [(p.x, p.y) for p in points]
    fit = circle_fit_2d(pts2)
    if not fit:
        return None
    axial = sum(axis_coord(p, axis) for p in points) / float(len(points))
    center = point_from_cross_axis(fit["center_2d"], axial, axis)
    fit["axis"] = axis
    fit["center"] = center
    fit["axial"] = float(axial)
    return fit


def best_axis_fit(points, bbox_diag):
    max_r = min(MAX_RADIUS_ABSOLUTE, max(10.0, bbox_diag * 0.35))
    fits = []
    for axis in ("X", "Y", "Z"):
        fit = axis_circle_fit(points, axis)
        if not fit:
            continue
        r = float(fit["radius"])
        if not (MIN_RADIUS <= r <= max_r):
            continue
        if fit["rel_spread"] > MAX_REL_SPREAD_SUSPECT:
            continue
        fits.append(fit)
    if not fits:
        return None
    fits.sort(key=lambda f: (f["rel_spread"], -f["confidence"], f["radius"]))
    return fits[0]


def e074_pca_circle(points):
    """Independent 3D plane-circle confirmation. Bounded point count only."""
    if np is None or len(points) < MIN_POINTS:
        return None
    try:
        arr = np.asarray([(p.x, p.y, p.z) for p in points], dtype=float)
        center = np.mean(arr, axis=0)
        centered = arr - center
        cov = np.cov(centered.T)
        vals, vecs = np.linalg.eigh(cov)
        normal = vecs[:, int(np.argmin(vals))]
        n_norm = float(np.linalg.norm(normal))
        if n_norm <= 1e-12:
            return None
        normal = normal / n_norm
        # Tangent basis
        if abs(normal[0]) > abs(normal[1]):
            u = np.asarray([-normal[2], 0.0, normal[0]], dtype=float)
        else:
            u = np.asarray([0.0, normal[2], -normal[1]], dtype=float)
        u_norm = float(np.linalg.norm(u))
        if u_norm <= 1e-12:
            return None
        u = u / u_norm
        v = np.cross(normal, u)
        v = v / float(np.linalg.norm(v))
        pts2 = []
        for row in arr:
            d = row - center
            pts2.append((float(np.dot(d, u)), float(np.dot(d, v))))
        fit = circle_fit_2d(pts2)
        if not fit:
            return None
        c3 = center + u * fit["center_2d"][0] + v * fit["center_2d"][1]
        align = {"X": abs(float(normal[0])), "Y": abs(float(normal[1])), "Z": abs(float(normal[2]))}
        best_axis = max(align.keys(), key=lambda a: align[a])
        return {
            "center": App.Vector(float(c3[0]), float(c3[1]), float(c3[2])),
            "radius": float(fit["radius"]),
            "rms": float(fit["rms"]),
            "rel_spread": float(fit["rel_spread"]),
            "confidence": float(fit["confidence"]),
            "best_axis": best_axis,
            "axis_alignment": float(align[best_axis]),
        }
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Lightweight ring marker output
# -----------------------------------------------------------------------------
def make_circle_edge(radius, center, axis):
    normal = AXIS_VECTORS.get(axis, App.Vector(0, 0, 1))
    return Part.makeCircle(float(radius), center, normal)


def make_ring_marker(doc, group, label, center, axis, radius, color, stage, metadata=None):
    try:
        edge = make_circle_edge(radius, center, axis)
        obj = doc.addObject("Part::Feature", safe_name(label))
        obj.Label = label
        obj.Shape = Part.Compound([edge])
        try:
            obj.ViewObject.LineColor = color
            obj.ViewObject.ShapeColor = color
            obj.ViewObject.LineWidth = 3.0
        except Exception:
            pass
        if group is not None:
            group.addObject(obj)
        add_prop(obj, "App::PropertyString", "X1Checkpoint", VERSION)
        add_prop(obj, "App::PropertyString", "X1FeatureRole", "diagnostic")
        add_prop(obj, "App::PropertyString", "X1FeatureStage", stage)
        add_prop(obj, "App::PropertyString", "X1Axis", axis)
        add_prop(obj, "App::PropertyFloat", "X1Radius", float(radius))
        add_prop(obj, "App::PropertyFloat", "X1Diameter", float(radius) * 2.0)
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, bool):
                    add_prop(obj, "App::PropertyBool", key, bool(value))
                elif isinstance(value, int):
                    add_prop(obj, "App::PropertyInteger", key, int(value))
                elif isinstance(value, float):
                    add_prop(obj, "App::PropertyFloat", key, float(value))
                else:
                    add_prop(obj, "App::PropertyString", key, str(value))
        return obj
    except Exception as exc:
        warn(f"      marker failed: {label}: {exc}")
        return None


def make_stack_marker(doc, group, label, center_cross, axis, radius, axial_min, axial_max, color, metadata=None):
    try:
        p0 = point_from_cross_axis(center_cross, axial_min, axis)
        p1 = point_from_cross_axis(center_cross, axial_max, axis)
        e0 = make_circle_edge(radius, p0, axis)
        e1 = make_circle_edge(radius, p1, axis)
        line = Part.makeLine(p0, p1)
        obj = doc.addObject("Part::Feature", safe_name(label))
        obj.Label = label
        obj.Shape = Part.Compound([e0, e1, line])
        try:
            obj.ViewObject.LineColor = color
            obj.ViewObject.ShapeColor = color
            obj.ViewObject.LineWidth = 3.0
        except Exception:
            pass
        if group is not None:
            group.addObject(obj)
        add_prop(obj, "App::PropertyString", "X1Checkpoint", VERSION)
        add_prop(obj, "App::PropertyString", "X1FeatureRole", "diagnostic")
        add_prop(obj, "App::PropertyString", "X1FeatureStage", "one_ring_layer_stack")
        add_prop(obj, "App::PropertyString", "X1Axis", axis)
        add_prop(obj, "App::PropertyFloat", "X1Radius", float(radius))
        add_prop(obj, "App::PropertyFloat", "X1Depth", float(abs(axial_max - axial_min)))
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, bool):
                    add_prop(obj, "App::PropertyBool", key, bool(value))
                elif isinstance(value, int):
                    add_prop(obj, "App::PropertyInteger", key, int(value))
                elif isinstance(value, float):
                    add_prop(obj, "App::PropertyFloat", key, float(value))
                else:
                    add_prop(obj, "App::PropertyString", key, str(value))
        return obj
    except Exception as exc:
        warn(f"      stack marker failed: {label}: {exc}")
        return None


# -----------------------------------------------------------------------------
# Detector
# -----------------------------------------------------------------------------
class X1R20BFastBoundedDiagnostics:
    def __init__(self):
        self.doc = App.ActiveDocument or App.newDocument()
        self.start_time = time.time()
        self.stop_requested = False

    def over_budget(self):
        if self.stop_requested:
            return True
        if time.time() - self.start_time > TIME_BUDGET_SECONDS:
            self.stop_requested = True
            warn(f"  R18F FAST: soft time budget {TIME_BUDGET_SECONDS:.0f}s reached; stopping with partial diagnostics.")
            return True
        return False

    def get_shape(self, obj):
        try:
            shape = obj.Shape
            if shape and not shape.isNull():
                return shape
        except Exception:
            pass
        return None

    def run(self, selected):
        if np is None:
            err("R18F FAST requires numpy in the FreeCAD Python environment.")
            return
        root = add_group(self.doc, None, "X1_2026_R18F_FAST_Chamfer_Tolerant_Diagnostics")
        msg(f"\n=== {R20B_FAST_VERSION} started ===")
        msg(f"Selected objects: {len(selected)}")
        msg("Policy: diagnostic-only; R18B accepted-feature path unchanged")
        msg("FAST mode: g060 broad edge proposals disabled by default; chamfer-tolerant guarded stack markers only")
        msg(f"Soft time budget: {TIME_BUDGET_SECONDS:.0f}s")

        totals = defaultdict(int)
        for index, obj in enumerate(selected, 1):
            if self.over_budget():
                break
            result = self.process_object(root, obj, index)
            for key, value in result.items():
                if isinstance(value, (int, float)):
                    totals[key] += int(value)
            pulse_gui()

        try:
            self.doc.recompute()
        except Exception as exc:
            warn(f"Final recompute warning: {exc}")
        elapsed = time.time() - self.start_time
        msg(f"=== {R20B_FAST_VERSION} finished ===")
        msg(f"Total observations: {totals['observations']}")
        msg(f"Total e074 loop-circle markers: {totals['e074_markers']}")
        msg(f"Total one-ring/layer stack markers: {totals['stack_markers']}")
        msg(f"Total weak tessellation cluster markers: {totals['weak_markers']}")
        msg(f"Total suspect one-ring markers: {totals['suspect_markers']}")
        msg(f"Total markers: {totals['markers']}")
        msg(f"Stopped by time budget: {self.stop_requested}")
        msg(f"Processing time: {elapsed:.2f}s")
        msg("Output group: X1_2026_R18F_FAST_Chamfer_Tolerant_Diagnostics")

    def process_object(self, root, obj, index):
        label = getattr(obj, "Label", getattr(obj, "Name", f"Object_{index}"))
        msg(f"\nR18F FAST object {index}: {label}")
        shape = self.get_shape(obj)
        if shape is None:
            warn("  skipped: no Part.Shape")
            return defaultdict(int)

        bbox = shape.BoundBox
        bbox_diag = float(getattr(bbox, "DiagonalLength", 0.0) or 0.0)
        self.current_bbox_diag = bbox_diag
        face_count = len(getattr(shape, "Faces", []))
        edge_count = len(getattr(shape, "Edges", []))
        msg(f"  shape: faces={face_count} edges={edge_count} bbox_diag={bbox_diag:.3f}")

        obj_group = add_group(self.doc, root, f"R18F_FAST_{safe_name(label)}")
        g_e074 = add_group(self.doc, obj_group, "Fast_E074_Loop_Circles")
        g_stack = add_group(self.doc, obj_group, "Fast_One_Ring_Layer_Stacks")
        g_weak = add_group(self.doc, obj_group, "Fast_Weak_Tessellation_Clusters")
        g_suspect = add_group(self.doc, obj_group, "Fast_Suspect_One_Ring_Circles")
        g_disabled = add_group(self.doc, obj_group, "Skipped_Heavy_G060_Disabled")
        _ = g_disabled

        observations = self.collect_loop_observations(shape, bbox_diag)
        if len(observations) < 8 and not self.over_budget():
            observations.extend(self.collect_closed_edge_observations(shape, bbox_diag, seen_sources={o['source'] for o in observations}))

        stacks = self.build_layer_stacks(observations)
        anchored_sources = self.stack_source_set(stacks)
        weak = self.build_weak_clusters(observations)
        suspects = self.pick_suspects(observations, stacks)

        e074_markers = self.emit_e074(g_e074, observations, anchored_sources)
        stack_markers = self.emit_stacks(g_stack, stacks)
        weak_markers = self.emit_weak(g_weak, weak)
        suspect_markers = self.emit_suspects(g_suspect, suspects)

        msg(f"  observations: {len(observations)}")
        msg(f"    inner-like={sum(1 for o in observations if o['inner'])} weak/outer-like={sum(1 for o in observations if not o['inner'])}")
        msg(f"  stacks: {len(stacks)} candidates, emitted={stack_markers}")
        msg(f"  weak clusters: {len(weak)} candidates, guarded emitted={weak_markers}")
        if EMIT_UNANCHORED_SUSPECT_MARKERS:
            msg(f"  suspects: {len(suspects)} candidates, emitted={suspect_markers}")
        else:
            msg(f"  suspects: {len(suspects)} candidates, emitted=0 (suppressed unanchored R18F guard)")
        msg("  g060 broad edge proposals: skipped in FAST mode")

        markers = e074_markers + stack_markers + weak_markers + suspect_markers
        return {
            "observations": len(observations),
            "e074_markers": e074_markers,
            "stack_markers": stack_markers,
            "weak_markers": weak_markers,
            "suspect_markers": suspect_markers,
            "markers": markers,
            "stacks": list(stacks),
        }

    def make_observation(self, source, source_kind, points, fit, efit, inner):
        axis = fit["axis"]
        center = fit["center"]
        e_radius = float(efit["radius"]) if efit else 0.0
        radius = float(fit["radius"])
        radius_delta = abs(e_radius - radius) / max(radius, 1e-9) if efit else 9.0
        e_confirmed = bool(efit and efit["rel_spread"] <= MAX_REL_SPREAD_CIRCLE and radius_delta <= 0.60)
        return {
            "source": source,
            "source_kind": source_kind,
            "axis": axis,
            "center": center,
            "cross": cross_coords(center, axis),
            "axial": axis_coord(center, axis),
            "radius": radius,
            "rms": float(fit["rms"]),
            "rel_spread": float(fit["rel_spread"]),
            "confidence": float(fit["confidence"]),
            "point_count": int(fit["point_count"]),
            "inner": bool(inner),
            "e074_confirmed": e_confirmed,
            "e074_radius": e_radius,
            "e074_rel_spread": float(efit["rel_spread"]) if efit else 9.0,
            "e074_axis": efit.get("best_axis", "") if efit else "",
            "e074_axis_alignment": float(efit.get("axis_alignment", 0.0)) if efit else 0.0,
            "e074_radius_delta": float(radius_delta),
        }

    def collect_loop_observations(self, shape, bbox_diag):
        observations = []
        seen = set()
        face_limit_hit = False
        wire_limit_hit = False
        wire_count = 0
        all_faces = list(getattr(shape, "Faces", []))
        faces, face_limit_hit = select_evenly(all_faces, MAX_FACES_PER_OBJECT)
        for local_face_index, face in enumerate(faces, 1):
            if self.over_budget():
                break
            if local_face_index % GUI_PULSE_EVERY == 0:
                msg(f"    distributed face-wire pass: {local_face_index}/{len(faces)} sampled faces of {len(all_faces)}, observations={len(observations)}")
                pulse_gui()
            # Preserve approximate global face id for diagnostics where possible.
            if face_limit_hit and len(faces) > 1 and len(all_faces) > 1:
                face_index = int(round((local_face_index - 1) * (len(all_faces) - 1) / float(len(faces) - 1))) + 1
            else:
                face_index = local_face_index
            try:
                wires = list(face.Wires)
            except Exception:
                continue
            for wire_index, wire in enumerate(wires, 1):
                wire_count += 1
                if wire_count > MAX_WIRES_PER_OBJECT:
                    wire_limit_hit = True
                    break
                points = sample_wire(wire, SAMPLES_PER_WIRE_EDGE)
                if len(points) < MIN_POINTS:
                    continue
                fit = best_axis_fit(points, bbox_diag)
                if not fit:
                    continue
                efit = e074_pca_circle(points)
                source = f"face_{face_index}_wire_{wire_index}"
                key = (fit["axis"], round(fit["center"].x, 3), round(fit["center"].y, 3), round(fit["center"].z, 3), round(fit["radius"], 3))
                if key in seen:
                    continue
                seen.add(key)
                observations.append(self.make_observation(
                    source=source,
                    source_kind="face_inner_wire" if wire_index > 1 else "face_outer_or_unknown_wire",
                    points=points,
                    fit=fit,
                    efit=efit,
                    inner=(wire_index > 1),
                ))
            if wire_limit_hit:
                break
        if face_limit_hit:
            warn(f"  distributed face cap applied: sampled {len(faces)} of {len(all_faces)} faces across whole object")
        if wire_limit_hit:
            warn(f"  wire cap applied: processed first {MAX_WIRES_PER_OBJECT} wires only")
        return observations

    def collect_closed_edge_observations(self, shape, bbox_diag, seen_sources):
        observations = []
        all_edges = list(getattr(shape, "Edges", []))
        edges, edge_limit_hit = select_evenly(all_edges, MAX_EDGES_FALLBACK)
        if edge_limit_hit:
            warn(f"  selective closed-edge fallback: sampled {len(edges)} of {len(all_edges)} edges across whole object")
        else:
            msg(f"  selective closed-edge fallback: processing all {len(edges)} edges")
        seen_keys = set()
        for edge_index, edge in enumerate(edges, 1):
            if self.over_budget():
                break
            if edge_index % GUI_PULSE_EVERY == 0:
                msg(f"    selective closed-edge fallback: {edge_index}/{len(edges)} sampled edges, observations={len(observations)}")
                pulse_gui()
            # Very cheap prefilters first. This keeps Mesh025-like objects available
            # while preventing the old broad g060 freeze.
            length = edge_length(edge)
            if length < 0.25 or length > max(20.0, bbox_diag * 1.25):
                continue
            if not edge_may_be_closed(edge):
                continue
            points = downsample(sample_edge(edge, SAMPLES_PER_CLOSED_EDGE), MAX_POINTS_PER_LOOP)
            if len(points) < MIN_POINTS:
                continue
            fit = best_axis_fit(points, bbox_diag)
            if not fit:
                continue
            # For edge-only tessellation evidence, keep loose circles but avoid
            # extremely noisy silhouette loops.
            if fit["rel_spread"] > MAX_REL_SPREAD_SUSPECT:
                continue
            efit = e074_pca_circle(points)
            source = f"selective_closed_edge_{edge_index}"
            if source in seen_sources:
                continue
            key = (fit["axis"], round(fit["center"].x, 2), round(fit["center"].y, 2), round(fit["center"].z, 2), round(fit["radius"], 2))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            observations.append(self.make_observation(
                source=source,
                source_kind="selective_closed_edge_weak",
                points=points,
                fit=fit,
                efit=efit,
                inner=False,
            ))
        return observations

    def grid_key(self, obs, grid=CENTER_GRID):
        c0, c1 = obs["cross"]
        return (obs["axis"], int(round(c0 / grid)), int(round(c1 / grid)))

    def build_layer_stacks(self, observations):
        buckets = defaultdict(list)
        for obs in observations:
            # Need circles good enough to represent rings/layers.
            if obs["rel_spread"] > MAX_REL_SPREAD_SUSPECT:
                continue
            buckets[self.grid_key(obs, CENTER_GRID)].append(obs)
        stacks = []
        for key, members in buckets.items():
            if len(members) < 2:
                continue
            axial = sorted([float(m["axial"]) for m in members])
            span = max(axial) - min(axial)
            if span < STACK_MIN_AXIAL_SPAN:
                continue
            radii = [float(m["radius"]) for m in members]
            rmin, rmax = min(radii), max(radii)
            if rmax / max(rmin, 1e-9) > STACK_RADIUS_RATIO_MAX:
                continue
            radius_mean = sum(radii) / len(radii)
            radius_range_ratio = (rmax - rmin) / max(radius_mean, 1e-9)
            radius_delta_ratio = (rmax - rmin) / max(rmax, 1e-9)
            if not self.marker_radius_allowed(rmax):
                continue
            inner_count = sum(1 for m in members if m["inner"])
            e074_count = sum(1 for m in members if m["e074_confirmed"])

            normal_stack = (
                radius_range_ratio <= MAX_STACK_RADIUS_RANGE_RATIO
                and (e074_count >= MIN_STACK_E074_CONFIRMED or inner_count >= MIN_STACK_INNER_MEMBERS)
            )
            chamfer_stack = (
                len(members) >= MIN_CHAMFER_STACK_MEMBERS
                and e074_count >= MIN_CHAMFER_STACK_E074_CONFIRMED
                and radius_delta_ratio >= MIN_CHAMFER_STACK_RADIUS_DELTA_RATIO
                and radius_range_ratio <= MAX_CHAMFER_STACK_RADIUS_RANGE_RATIO
            )
            if not normal_stack and not chamfer_stack:
                continue
            stack_kind = "chamfer_or_step_stack" if chamfer_stack and not normal_stack else "layer_stack"
            axis = members[0]["axis"]
            cross = (
                sum(m["cross"][0] for m in members) / len(members),
                sum(m["cross"][1] for m in members) / len(members),
            )
            stacks.append({
                "axis": axis,
                "cross": cross,
                "axial_min": min(axial),
                "axial_max": max(axial),
                "radius_min": rmin,
                "radius_max": rmax,
                "radius_mean": radius_mean,
                "radius_range_ratio": radius_range_ratio,
                "radius_delta_ratio": radius_delta_ratio,
                "stack_kind": stack_kind,
                "member_count": len(members),
                "inner_members": inner_count,
                "e074_confirmed_members": e074_count,
                "sources": ",".join(m["source"] for m in members[:8]),
            })
        stacks.sort(key=lambda s: (-s["e074_confirmed_members"], -s["inner_members"], -s["member_count"], s["axis"]))
        return stacks

    def build_weak_clusters(self, observations):
        weak = [o for o in observations if not o["inner"]]
        buckets = defaultdict(list)
        for obs in weak:
            key = self.grid_key(obs, WEAK_CLUSTER_GRID) + (int(round(obs["radius"] / 2.0)),)
            buckets[key].append(obs)
        clusters = []
        for members in buckets.values():
            confirmed = sum(1 for m in members if m["e074_confirmed"])
            if len(members) < 2 and confirmed < 1:
                continue
            radii = [m["radius"] for m in members]
            axis = members[0]["axis"]
            center = App.Vector(
                sum(m["center"].x for m in members) / len(members),
                sum(m["center"].y for m in members) / len(members),
                sum(m["center"].z for m in members) / len(members),
            )
            radius_mean = sum(radii) / len(radii)
            radius_range_ratio = (max(radii) - min(radii)) / max(radius_mean, 1e-9)
            marker_allowed = (
                len(members) >= MIN_WEAK_CLUSTER_MEMBERS
                and confirmed >= MIN_WEAK_CLUSTER_E074_CONFIRMED
                and radius_range_ratio <= MAX_WEAK_CLUSTER_RADIUS_RANGE_RATIO
                and self.marker_radius_allowed(radius_mean)
            )
            clusters.append({
                "axis": axis,
                "center": center,
                "radius_mean": radius_mean,
                "radius_min": min(radii),
                "radius_max": max(radii),
                "radius_range_ratio": radius_range_ratio,
                "marker_allowed": marker_allowed,
                "member_count": len(members),
                "e074_confirmed_members": confirmed,
                "sources": ",".join(m["source"] for m in members[:8]),
            })
        clusters.sort(key=lambda c: (-c["e074_confirmed_members"], -c["member_count"], c["axis"]))
        return clusters

    def pick_suspects(self, observations, stacks):
        stacked_sources = set()
        for stack in stacks:
            for src in stack.get("sources", "").split(","):
                if src:
                    stacked_sources.add(src)
        suspects = []
        for obs in observations:
            if obs["source"] in stacked_sources:
                continue
            if obs["inner"] or obs["e074_confirmed"] or obs["rel_spread"] <= MAX_REL_SPREAD_CIRCLE:
                suspects.append(obs)
        suspects.sort(key=lambda o: (not o["e074_confirmed"], not o["inner"], o["rel_spread"], -o["point_count"]))
        return suspects[:MAX_SUSPECT_MARKERS]

    def stack_source_set(self, stacks):
        sources = set()
        for stack in stacks:
            for src in str(stack.get("sources", "")).split(","):
                src = src.strip()
                if src:
                    sources.add(src)
        return sources

    def marker_radius_allowed(self, radius):
        bbox = float(getattr(self, "current_bbox_diag", 0.0) or 0.0)
        if bbox <= 1e-9:
            return True
        return float(radius) <= bbox * MAX_MARKER_RADIUS_FRACTION_OF_BBOX

    def emit_e074(self, group, observations, anchored_sources):
        emitted = 0
        for obs in observations:
            if emitted >= MAX_E074_MARKERS or self.over_budget():
                break
            if not obs["e074_confirmed"]:
                continue
            if obs["source"] not in anchored_sources:
                continue
            if not self.marker_radius_allowed(obs["radius"]):
                continue
            label = f"R18F_FAST_e074_{emitted+1:03d}_{obs['axis']}_r{obs['radius']:.3f}"
            obj = make_ring_marker(self.doc, group, label, obs["center"], obs["axis"], obs["radius"], COLORS["e074"], "e074_loop_circle", {
                "X1Source": obs["source"],
                "X1SourceKind": obs["source_kind"],
                "X1PointCount": obs["point_count"],
                "X1RelativeSpread": obs["rel_spread"],
                "X1E074RelativeSpread": obs["e074_rel_spread"],
                "X1E074RadiusDelta": obs["e074_radius_delta"],
                "X1InnerEvidence": obs["inner"],
            })
            if obj:
                emitted += 1
        return emitted

    def emit_stacks(self, group, stacks):
        emitted = 0
        for stack in stacks[:MAX_STACK_MARKERS]:
            if self.over_budget():
                break
            radius = max(stack["radius_mean"], stack["radius_max"])
            label = f"R18F_FAST_stack_{emitted+1:03d}_{stack['axis']}_layers_{stack['member_count']}_r{radius:.3f}"
            obj = make_stack_marker(self.doc, group, label, stack["cross"], stack["axis"], radius, stack["axial_min"], stack["axial_max"], COLORS["stack"], {
                "X1RadiusMin": stack["radius_min"],
                "X1RadiusMax": stack["radius_max"],
                "X1RadiusRangeRatio": stack.get("radius_range_ratio", 0.0),
                "X1RadiusDeltaRatio": stack.get("radius_delta_ratio", 0.0),
                "X1DiagnosticStackKind": stack.get("stack_kind", "layer_stack"),
                "X1MemberCount": stack["member_count"],
                "X1InnerMembers": stack["inner_members"],
                "X1E074ConfirmedMembers": stack["e074_confirmed_members"],
                "X1Sources": stack["sources"],
            })
            if obj:
                emitted += 1
                msg(f"    FAST stack {emitted:03d}: kind={stack.get('stack_kind', 'layer_stack')} axis={stack['axis']} members={stack['member_count']} r={stack['radius_min']:.3f}..{stack['radius_max']:.3f} depth={abs(stack['axial_max']-stack['axial_min']):.3f} e074={stack['e074_confirmed_members']}")
                pulse_gui()
        return emitted

    def emit_weak(self, group, clusters):
        emitted = 0
        for cl in clusters[:MAX_WEAK_CLUSTER_MARKERS]:
            if self.over_budget():
                break
            if not cl.get("marker_allowed", False):
                continue
            label = f"R18F_FAST_weak_cluster_{emitted+1:03d}_{cl['axis']}_r{cl['radius_mean']:.3f}"
            obj = make_ring_marker(self.doc, group, label, cl["center"], cl["axis"], cl["radius_mean"], COLORS["weak"], "guarded_weak_tessellation_cluster", {
                "X1RadiusMin": cl["radius_min"],
                "X1RadiusMax": cl["radius_max"],
                "X1RadiusRangeRatio": cl["radius_range_ratio"],
                "X1MemberCount": cl["member_count"],
                "X1E074ConfirmedMembers": cl["e074_confirmed_members"],
                "X1Sources": cl["sources"],
            })
            if obj:
                emitted += 1
        return emitted

    def emit_suspects(self, group, suspects):
        emitted = 0
        if not EMIT_UNANCHORED_SUSPECT_MARKERS:
            return 0
        for obs in suspects[:MAX_SUSPECT_MARKERS]:
            if self.over_budget():
                break
            if not self.marker_radius_allowed(obs["radius"]):
                continue
            label = f"R18F_FAST_suspect_{emitted+1:03d}_{obs['axis']}_r{obs['radius']:.3f}"
            obj = make_ring_marker(self.doc, group, label, obs["center"], obs["axis"], obs["radius"], COLORS["suspect"], "suspect_one_ring_circle", {
                "X1Source": obs["source"],
                "X1SourceKind": obs["source_kind"],
                "X1PointCount": obs["point_count"],
                "X1RelativeSpread": obs["rel_spread"],
                "X1E074Confirmed": obs["e074_confirmed"],
                "X1InnerEvidence": obs["inner"],
            })
            if obj:
                emitted += 1
        return emitted




# =============================================================================

# R20B chamfer-aware reconciliation diagnostics
# =============================================================================

R20B_RECONCILE_MAX_STACKS = 16
R20B_RECONCILE_CENTER_FACTOR = 0.35
R20B_RECONCILE_CENTER_MIN = 1.25
R20B_RECONCILE_RADIUS_MATCH_FACTOR = 1.35
R20B_RECONCILE_CHAMFER_RADIUS_DELTA_RATIO = 0.08
R20B_RECONCILE_BODY_CLEARANCE_RATIO = 0.94
R20B_RECONCILE_MISSING_MIN_E074 = 2
R20B_RECONCILE_MISSING_MIN_INNER = 2
R20B_RECONCILE_COLOR_COVERED = (0.35, 0.65, 1.0)
R20B_RECONCILE_COLOR_CHAMFER = (1.0, 0.65, 0.05)
R20B_RECONCILE_COLOR_BODY = (0.15, 0.85, 0.35)
R20B_RECONCILE_COLOR_MISSING = (1.0, 0.25, 0.8)
R20B_RECONCILE_COLOR_PAIRED_MISSING = (0.95, 0.15, 1.0)
R20B_RECONCILE_COLOR_ACCEPTED_MOUTH = (1.0, 0.48, 0.05)
R20B_RECONCILE_COLOR_TESSELLATION = (0.65, 0.65, 0.65)

# R20B evidence-ledger additions. These do not promote or resize accepted
# cylinders. They only classify what the combined evidence suggests. The goal is
# to make Mesh008-style six-bore/chamfer cases readable while still keeping
# Mesh025-like tessellation-only evidence guarded.
R20B_LEDGER_CENTER_FACTOR = 0.48
R20B_LEDGER_CENTER_MIN = 1.50
R20B_LEDGER_ACCEPTED_MOUTH_RANGE_RATIO = 0.045
R20B_LEDGER_MISSING_CHAMFER_RANGE_RATIO = 0.075
R20B_LEDGER_SMALL_FEATURE_MAX_BBOX_FRACTION = 0.16
R20B_LEDGER_BODY_RADIUS_POLICY = "smaller_layer_radius_when_chamfer_like_else_mean"


def r20b_axis_cross_distance_for_primitive(stack, primitive):
    """Distance between a FAST stack centerline and an accepted primitive centerline."""
    try:
        axis = str(stack.get("axis", "Z")).upper()
        if axis != str(primitive.get("axis_hint", "FREE")).upper():
            return 999999.0
        data = primitive_start_end_axis(primitive)
        if data is None:
            return 999999.0
        start, _end, prim_axis, _height = data
        axial_mid = 0.5 * (float(stack.get("axial_min", 0.0)) + float(stack.get("axial_max", 0.0)))
        center = point_from_cross_axis(stack.get("cross", (0.0, 0.0)), axial_mid, axis)
        return line_distance_parallel(center, axis_vector(axis), start, prim_axis)
    except Exception:
        return 999999.0


def r20b_nearest_accepted_for_stack(stack, accepted_primitives):
    """Find nearest accepted same-axis primitive for a FAST stack."""
    best = None
    radius_max = float(stack.get("radius_max", stack.get("radius_mean", 0.0)))
    radius_mean = float(stack.get("radius_mean", radius_max))
    for prim in accepted_primitives or []:
        if str(prim.get("axis_hint", "FREE")).upper() != str(stack.get("axis", "Z")).upper():
            continue
        prim_radius = float(prim.get("radius", 0.0))
        if prim_radius <= X1_MIN_RADIUS:
            continue
        dist = r20b_axis_cross_distance_for_primitive(stack, prim)
        center_limit = max(
            R20B_RECONCILE_CENTER_MIN,
            R20B_RECONCILE_CENTER_FACTOR * max(radius_max, prim_radius),
        )
        radius_ratio = max(radius_max, prim_radius) / max(min(radius_max, prim_radius), 1.0e-9)
        if dist > center_limit:
            continue
        if radius_ratio > R20B_RECONCILE_RADIUS_MATCH_FACTOR:
            continue
        item = {
            "primitive": prim,
            "distance": dist,
            "center_limit": center_limit,
            "primitive_radius": prim_radius,
            "radius_ratio": radius_ratio,
            "radius_delta": abs(radius_mean - prim_radius),
        }
        if best is None or (item["distance"], item["radius_ratio"]) < (best["distance"], best["radius_ratio"]):
            best = item
    return best


def r20b_classify_stack(stack, accepted_primitives):
    """Classify FAST layer-stack evidence without promoting accepted cylinders.

    R20B keeps R18H's stable-bore reconciliation but adds two important cases:
    - accepted_bore_may_be_chamfer_mouth_or_mixed_radius: an accepted cylinder
      is on the same centerline as a changing-radius stack, so its radius may be
      mouth/chamfer-influenced rather than a pure body/core radius.
    - missing_bore_with_chamfer_candidate: a strong paired-layer stack has no
      accepted bore and shows a smaller/larger radius pair. On Mesh008 this is
      the expected pattern for the two missed small bores with chamfers.
    """
    nearest = r20b_nearest_accepted_for_stack(stack, accepted_primitives)
    rmin = float(stack.get("radius_min", stack.get("radius_mean", 0.0)))
    rmax = float(stack.get("radius_max", stack.get("radius_mean", 0.0)))
    rmean = float(stack.get("radius_mean", rmax))
    radius_delta_ratio = float(stack.get("radius_delta_ratio", 0.0))
    radius_range_ratio = float(stack.get("radius_range_ratio", 0.0))
    kind = str(stack.get("stack_kind", "layer_stack"))
    e074 = int(stack.get("e074_confirmed_members", 0))
    inner = int(stack.get("inner_members", 0))
    member_count = int(stack.get("member_count", 0))

    chamfer_like = (
        kind == "chamfer_or_step_stack"
        or radius_delta_ratio >= R20B_RECONCILE_CHAMFER_RADIUS_DELTA_RATIO
        or radius_range_ratio >= R20B_RECONCILE_CHAMFER_RADIUS_DELTA_RATIO
        or radius_range_ratio >= R20B_LEDGER_ACCEPTED_MOUTH_RANGE_RATIO
    )
    strong_pair = (e074 >= R20B_RECONCILE_MISSING_MIN_E074 or inner >= R20B_RECONCILE_MISSING_MIN_INNER)
    smallish = True
    try:
        # bbox_diag may not be available on stack, so this stays permissive.
        bbox_diag = float(stack.get("bbox_diag", 0.0) or 0.0)
        if bbox_diag > 1.0e-9:
            smallish = rmax <= bbox_diag * R20B_LEDGER_SMALL_FEATURE_MAX_BBOX_FRACTION
    except Exception:
        smallish = True

    if nearest is None:
        if strong_pair and chamfer_like and radius_range_ratio >= R20B_LEDGER_MISSING_CHAMFER_RANGE_RATIO:
            return "missing_bore_with_chamfer_candidate", "FAST paired-layer stack has no accepted bore and shows body/mouth radius split; treat as missing bore with chamfer, not as a random circle", nearest
        if strong_pair:
            return "missing_feature_candidate", "FAST stack has no matching accepted bore but has strong paired-layer evidence", nearest
        return "tessellation_only_unanchored", "FAST stack has no accepted-bore anchor and insufficient paired-layer strength", nearest

    pr = float(nearest.get("primitive_radius", 0.0))
    accepted_inside_stack_band = (rmin <= pr <= rmax) if rmax >= rmin else False
    accepted_near_outer = pr >= rmax * R20B_RECONCILE_BODY_CLEARANCE_RATIO
    has_smaller_body = rmin < pr * max(0.985, R20B_RECONCILE_BODY_CLEARANCE_RATIO)

    if chamfer_like and accepted_inside_stack_band:
        return "accepted_bore_may_be_chamfer_mouth_or_mixed_radius", "accepted cylinder lies inside a changing-radius FAST layer band; radius may be chamfer/mouth-influenced and needs body/core comparison", nearest
    if chamfer_like and accepted_near_outer and has_smaller_body:
        return "chamfer_mouth_with_smaller_body_candidate", "accepted radius likely follows mouth/chamfer layer; FAST stack exposes smaller body/core radius", nearest
    if chamfer_like:
        return "chamfer_or_step_transition", "FAST stack radius changes across layers; keep as transition diagnostic", nearest
    if abs(rmean - pr) <= max(0.15, 0.06 * max(rmean, pr)):
        return "already_covered_by_stable_bore", "FAST stack confirms an already accepted bore", nearest
    return "fast_confirmed_layer_candidate", "FAST stack is near an accepted bore but radius differs enough to keep diagnostic-only", nearest

def r20b_stack_marker_radius(stack, classification):
    """Prefer body/core radius for chamfer/body cases; otherwise use visible stack evidence."""
    rmin = float(stack.get("radius_min", stack.get("radius_mean", 0.0)))
    rmax = float(stack.get("radius_max", stack.get("radius_mean", 0.0)))
    rmean = float(stack.get("radius_mean", rmax))
    if classification in (
        "chamfer_mouth_with_smaller_body_candidate",
        "accepted_bore_may_be_chamfer_mouth_or_mixed_radius",
        "missing_bore_with_chamfer_candidate",
    ):
        return max(X1_MIN_RADIUS, rmin)
    if classification in ("chamfer_or_step_transition", "missing_feature_candidate"):
        return max(X1_MIN_RADIUS, rmean)
    return max(X1_MIN_RADIUS, rmax)


def r20b_stack_body_mouth_text(stack):
    """Readable R20B body/mouth pair hint for console and metadata."""
    rmin = float(stack.get("radius_min", stack.get("radius_mean", 0.0)))
    rmax = float(stack.get("radius_max", stack.get("radius_mean", 0.0)))
    if rmax > rmin * (1.0 + 1.0e-6):
        return "body≈%.3f mouth≈%.3f" % (rmin, rmax)
    return "single≈%.3f" % rmax

def r20b_reconciliation_group_for_class(doc, parent, classification):
    if classification == "already_covered_by_stable_bore":
        return ensure_named_child_group(doc, parent, "01_Stable_Bore_Confirmed", "01 Stable Bore Confirmed")
    if classification == "accepted_bore_may_be_chamfer_mouth_or_mixed_radius":
        return ensure_named_child_group(doc, parent, "02_Accepted_Bore_May_Be_Chamfer_Mouth", "02 Accepted Bore May Be Chamfer Mouth")
    if classification == "chamfer_mouth_with_smaller_body_candidate":
        return ensure_named_child_group(doc, parent, "03_Chamfer_Mouth_With_Body_Candidates", "03 Chamfer Mouth + Body/Core Candidates")
    if classification == "chamfer_or_step_transition":
        return ensure_named_child_group(doc, parent, "04_Chamfer_Or_Step_Transitions", "04 Chamfer / Step Transitions")
    if classification == "missing_bore_with_chamfer_candidate":
        return ensure_named_child_group(doc, parent, "05_Paired_Missing_Bore_Chamfer_Candidates", "05 Paired Missing Bore + Chamfer Candidates")
    if classification == "missing_feature_candidate":
        return ensure_named_child_group(doc, parent, "06_Other_Missing_Feature_Candidates", "06 Other Missing Feature Candidates")
    if classification == "tessellation_only_unanchored":
        return ensure_named_child_group(doc, parent, "07_Tessellation_Only_Unanchored", "07 Tessellation-Only Unanchored")
    return ensure_named_child_group(doc, parent, "08_Other_FAST_Reconciliation", "08 Other FAST Reconciliation")

def emit_chamfer_aware_reconciliation_markers(doc, parent_group, accepted_primitives, rejected_groups, fast_stacks, source_obj, bb):
    """R20B diagnostic-only evidence ledger for stable bores, FAST stacks, and rejected one-rings.

    This intentionally does not change accepted cylinders. It adds a separate
    visual/metadata layer so six-bore + chamfer cases can be read from both
    sides/layers while Mesh025-style tessellation-only evidence remains guarded.
    """
    totals = defaultdict(int)
    if parent_group is None:
        return totals
    stacks = list(fast_stacks or [])[:int(R20B_RECONCILE_MAX_STACKS)]
    if not stacks:
        x1_msg("  R20B evidence-ledger reconciliation: 0 FAST stacks to classify")
        return totals

    # Summarize one-ring rejected evidence by axis/radius.  This is printed only;
    # it helps compare the FAST layer stacks against the conservative rejected
    # groups without promoting those one-ring groups.
    one_ring_rejected = []
    try:
        for group, reason in rejected_groups or []:
            robs = list(group.get("observations", [])) if isinstance(group, dict) else []
            if len(robs) != 1:
                continue
            o = robs[0]
            one_ring_rejected.append({
                "axis": axis_hint(group.get("axis", axis_vector("Z"))) if isinstance(group, dict) else "?",
                "radius": float(o.get("radius", 0.0)),
                "center": o.get("center", None),
                "reason": str(reason),
                "source": str(o.get("source", "?")),
            })
    except Exception:
        one_ring_rejected = []

    for index, stack in enumerate(stacks, start=1):
        classification, reason, nearest = r20b_classify_stack(stack, accepted_primitives)
        target_group = r20b_reconciliation_group_for_class(doc, parent_group, classification)
        radius = r20b_stack_marker_radius(stack, classification)
        axis = str(stack.get("axis", "Z")).upper()
        color = R20B_RECONCILE_COLOR_COVERED
        if classification == "accepted_bore_may_be_chamfer_mouth_or_mixed_radius":
            color = R20B_RECONCILE_COLOR_ACCEPTED_MOUTH
            totals["accepted_mouth_markers"] += 1
            totals["chamfer_mouth_markers"] += 1
        elif classification == "chamfer_mouth_with_smaller_body_candidate":
            color = R20B_RECONCILE_COLOR_BODY
            totals["body_candidate_markers"] += 1
        elif classification == "chamfer_or_step_transition":
            color = R20B_RECONCILE_COLOR_CHAMFER
            totals["chamfer_mouth_markers"] += 1
        elif classification == "missing_bore_with_chamfer_candidate":
            color = R20B_RECONCILE_COLOR_PAIRED_MISSING
            totals["paired_missing_bore_chamfer_markers"] += 1
            totals["missing_candidate_markers"] += 1
        elif classification == "missing_feature_candidate":
            color = R20B_RECONCILE_COLOR_MISSING
            totals["missing_candidate_markers"] += 1
        elif classification == "already_covered_by_stable_bore":
            totals["covered_markers"] += 1
        elif classification == "tessellation_only_unanchored":
            color = R20B_RECONCILE_COLOR_TESSELLATION
            totals["tessellation_only_markers"] += 1
        else:
            totals["other_markers"] += 1

        body_mouth = r20b_stack_body_mouth_text(stack)
        label = "R20B_ledger_%03d_%s_%s_r%.3f" % (index, axis, classification[:20], radius)
        metadata = {
            "X1FeatureFamily": "evidence_ledger_reconciliation",
            "X1FeatureRole": "diagnostic",
            "X1FeatureStage": "r20b_evidence_ledger_reconciliation",
            "X1Classification": classification,
            "X1Reason": reason,
            "X1Axis": axis,
            "X1MarkerRadiusPolicy": R20B_LEDGER_BODY_RADIUS_POLICY,
            "X1BodyMouthHint": body_mouth,
            "X1RadiusMin": float(stack.get("radius_min", 0.0)),
            "X1RadiusMean": float(stack.get("radius_mean", 0.0)),
            "X1RadiusMax": float(stack.get("radius_max", 0.0)),
            "X1RadiusDeltaRatio": float(stack.get("radius_delta_ratio", 0.0)),
            "X1RadiusRangeRatio": float(stack.get("radius_range_ratio", 0.0)),
            "X1AxialMin": float(stack.get("axial_min", 0.0)),
            "X1AxialMax": float(stack.get("axial_max", 0.0)),
            "X1MemberCount": int(stack.get("member_count", 0)),
            "X1InnerMembers": int(stack.get("inner_members", 0)),
            "X1E074ConfirmedMembers": int(stack.get("e074_confirmed_members", 0)),
            "X1DiagnosticStackKind": str(stack.get("stack_kind", "layer_stack")),
            "X1Sources": str(stack.get("sources", "")),
        }
        if nearest is not None:
            metadata.update({
                "X1NearestAcceptedRadius": float(nearest.get("primitive_radius", 0.0)),
                "X1NearestAcceptedDistance": float(nearest.get("distance", 0.0)),
                "X1NearestAcceptedRadiusRatio": float(nearest.get("radius_ratio", 0.0)),
                "X1NearestAcceptedProfile": str(nearest.get("primitive", {}).get("profile", "")),
            })
        obj = make_stack_marker(
            doc,
            target_group,
            label,
            stack.get("cross", (0.0, 0.0)),
            axis,
            radius,
            float(stack.get("axial_min", 0.0)),
            float(stack.get("axial_max", 0.0)),
            color,
            metadata,
        )
        if obj:
            totals["markers"] += 1
            totals["ledger_entries"] += 1
            x1_msg(
                "  X1 R20B evidence ledger %03d: class=%s axis=%s marker_r=%.3f stack_r=%.3f..%.3f %s depth=%.3f nearest_r=%.3f reason=%s" % (
                    index,
                    classification,
                    axis,
                    radius,
                    float(stack.get("radius_min", 0.0)),
                    float(stack.get("radius_max", 0.0)),
                    body_mouth,
                    abs(float(stack.get("axial_max", 0.0)) - float(stack.get("axial_min", 0.0))),
                    float(nearest.get("primitive_radius", 0.0)) if nearest else 0.0,
                    reason,
                )
            )
    if one_ring_rejected:
        x1_msg("  R20B one-ring rejected evidence ledger: %d conservative rejected openings kept as context only" % len(one_ring_rejected))
        for i, o in enumerate(one_ring_rejected[:8], start=1):
            x1_msg("    one-ring %02d: axis=%s r=%.3f source=%s reason=%s" % (i, o.get("axis", "?"), o.get("radius", 0.0), str(o.get("source", "?")), o.get("reason", "")))
        if len(one_ring_rejected) > 8:
            x1_msg("    ... %d more one-ring rejected openings hidden by limit" % (len(one_ring_rejected) - 8))

    x1_msg(
        "  R20B evidence-ledger reconciliation: emitted %d markers (covered=%d, accepted_mouth=%d, chamfer/transition=%d, body/core=%d, paired_missing_bore_chamfer=%d, missing=%d, tessellation_only=%d)" % (
            int(totals.get("markers", 0)),
            int(totals.get("covered_markers", 0)),
            int(totals.get("accepted_mouth_markers", 0)),
            int(totals.get("chamfer_mouth_markers", 0)),
            int(totals.get("body_candidate_markers", 0)),
            int(totals.get("paired_missing_bore_chamfer_markers", 0)),
            int(totals.get("missing_candidate_markers", 0)),
            int(totals.get("tessellation_only_markers", 0)),
        )
    )
    return totals


# R20B embedded R18F FAST diagnostic bridge
# =============================================================================


def x1_r20b_emit_fast_chamfer_tolerant_diagnostics(doc, fast_group, obj, obj_index):
    """Run R18F FAST diagnostics inside the R20B per-object feature tree.

    This is diagnostic-only.  It must never modify the accepted R18B/R18A
    primitive path.  It only adds the R18F evidence groups below:

        05 FAST Tessellation / Chamfer Diagnostics
            R18F_FAST_<object label>
                Fast_E074_Loop_Circles
                Fast_One_Ring_Layer_Stacks
                Fast_Weak_Tessellation_Clusters
                Fast_Suspect_One_Ring_Circles
                Skipped_Heavy_G060_Disabled

    R18F's current guards keep weak clusters and unanchored one-ring suspects
    suppressed by default while preserving useful layer/chamfer stack evidence.
    """
    empty = defaultdict(int)
    if fast_group is None:
        return empty
    if np is None:
        x1_warn("  R20B FAST diagnostics skipped: numpy is not available in this FreeCAD Python environment")
        return empty
    try:
        detector = X1R20BFastBoundedDiagnostics()
        detector.doc = doc
        result = detector.process_object(fast_group, obj, obj_index)
        if result is None:
            return empty
        return result
    except Exception as exc:
        x1_warn("  R20B FAST diagnostics failed for %s: %s" % (getattr(obj, "Label", getattr(obj, "Name", "?")), exc))
        return empty


# =============================================================================
# R20B tessellated axis-side probe
# =============================================================================


def r20b_axis_coord(point, axis_name):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return float(point.x)
    if axis_name == "Y":
        return float(point.y)
    return float(point.z)


def r20b_cross_uv(point, axis_name):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return (float(point.y), float(point.z))
    if axis_name == "Y":
        return (float(point.x), float(point.z))
    return (float(point.x), float(point.y))


def r20b_point_from_axis_uv(axis_name, axis_value_coord, u, v):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return v_new(axis_value_coord, u, v)
    if axis_name == "Y":
        return v_new(u, axis_value_coord, v)
    return v_new(u, v, axis_value_coord)


def r20b_axis_bounds(bb, axis_name):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return (float(bb.XMin), float(bb.XMax), float(bb.XLength))
    if axis_name == "Y":
        return (float(bb.YMin), float(bb.YMax), float(bb.YLength))
    return (float(bb.ZMin), float(bb.ZMax), float(bb.ZLength))


def r20b_cross_bounds(bb, axis_name):
    axis_name = str(axis_name).upper()
    if axis_name == "X":
        return (float(bb.YMin), float(bb.YMax), float(bb.ZMin), float(bb.ZMax))
    if axis_name == "Y":
        return (float(bb.XMin), float(bb.XMax), float(bb.ZMin), float(bb.ZMax))
    return (float(bb.XMin), float(bb.XMax), float(bb.YMin), float(bb.YMax))


def r20b_face_vertices(face):
    pts = []
    try:
        for vv in face.Vertexes:
            pts.append(App.Vector(vv.Point.x, vv.Point.y, vv.Point.z))
    except Exception:
        pass
    return unique_points(pts)


def r20b_face_normal(face):
    try:
        u0, u1, v0, v1 = face.ParameterRange
        n = face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1))
        return v_unit(App.Vector(n.x, n.y, n.z))
    except Exception:
        pass
    pts = r20b_face_vertices(face)
    if len(pts) >= 3:
        a = v_sub(pts[1], pts[0])
        b = v_sub(pts[2], pts[0])
        n = v_new(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)
        return v_unit(n)
    return v_new(0, 0, 1)


def r20b_collect_side_wall_points(shape, bb, axis_name, side_name):
    """Collect near-mouth points from tessellated side-wall/chamfer faces.

    This avoids the old broad point-slice problem by not fitting arbitrary slices.
    It only samples faces touching a selected outside side plane whose normals are
    not simply the outside cap normal.  Those faces are likely bore walls,
    chamfers, counterbore walls, slot walls, or other feature-side surfaces.
    """
    axis_name = str(axis_name).upper()
    side_sign = 1 if str(side_name) == "+" else -1
    axis_vec = axis_vector(axis_name)
    mn, mx, axis_len = r20b_axis_bounds(bb, axis_name)
    side_value = mx if side_sign > 0 else mn
    diag = bbox_diag(bb)
    side_band = max(float(X1_R20B_PROBE_SIDE_BAND_MIN), diag * float(X1_R20B_PROBE_SIDE_BAND_BBOX_FACTOR))

    try:
        faces = list(shape.Faces)
    except Exception:
        return []
    face_count = len(faces)
    if face_count <= 0:
        return []
    cap = int(X1_R20B_PROBE_FACE_SAMPLE_CAP)
    if face_count > cap:
        # Distributed scan, not first-N.  This preserves whole-object coverage
        # while keeping hard tessellated meshes responsive.
        idxs = sorted(set(int(round(i * (face_count - 1) / float(max(1, cap - 1)))) for i in range(cap)))
        selected_faces = [faces[i] for i in idxs]
    else:
        selected_faces = faces

    points = []
    for face in selected_faces:
        try:
            pts = r20b_face_vertices(face)
            if not pts:
                continue
            near = []
            for p in pts:
                if abs(r20b_axis_coord(p, axis_name) - side_value) <= side_band:
                    near.append(p)
            if not near:
                continue
            n = r20b_face_normal(face)
            # Exclude simple outer cap/side faces.  Keep wall/chamfer faces.
            if abs(v_dot(n, axis_vec)) > float(X1_R20B_SIDE_FACE_NORMAL_MAX_DOT):
                continue
            points.extend(near)
        except Exception:
            continue
    return unique_points(points)


def r20b_cluster_projected_points(points, axis_name, bb):
    if len(points) < int(X1_R20B_PROBE_MIN_SIDE_POINTS):
        return []
    if len(points) > int(X1_R20B_PROBE_MAX_SIDE_POINTS):
        step = max(1, int(math.ceil(len(points) / float(X1_R20B_PROBE_MAX_SIDE_POINTS))))
        points = points[::step]

    uvp = []
    for p in points:
        u, v = r20b_cross_uv(p, axis_name)
        uvp.append((u, v, p))
    if not uvp:
        return []

    u_vals = [x[0] for x in uvp]
    v_vals = [x[1] for x in uvp]
    u_span = max(u_vals) - min(u_vals)
    v_span = max(v_vals) - min(v_vals)
    span = max(u_span, v_span, 1.0e-9)
    cell = max(span / float(X1_R20B_CLUSTER_GRID_DIVISIONS), bbox_diag(bb) * 0.0025, 0.08)
    link = cell * 1.85
    link2 = link * link

    grid = {}
    for i, (u, v, p) in enumerate(uvp):
        key = (int(math.floor(u / cell)), int(math.floor(v / cell)))
        grid.setdefault(key, []).append(i)

    visited = set()
    clusters = []
    for start in range(len(uvp)):
        if start in visited:
            continue
        visited.add(start)
        q = [start]
        comp = []
        while q:
            idx = q.pop()
            comp.append(idx)
            u, v, _p = uvp[idx]
            key = (int(math.floor(u / cell)), int(math.floor(v / cell)))
            for du in (-1, 0, 1):
                for dv in (-1, 0, 1):
                    for nb in grid.get((key[0] + du, key[1] + dv), []):
                        if nb in visited:
                            continue
                        uu, vv, _pp = uvp[nb]
                        if (uu - u) * (uu - u) + (vv - v) * (vv - v) <= link2:
                            visited.add(nb)
                            q.append(nb)
        if len(comp) >= int(X1_R20B_CLUSTER_MIN_POINTS):
            clusters.append([uvp[i] for i in comp])
    return clusters


def r20b_candidate_from_cluster(cluster, axis_name, side_name, bb, side_value, source_label):
    pts2d = [(u, v) for (u, v, _p) in cluster]
    if len(pts2d) < int(X1_R20B_CLUSTER_MIN_POINTS):
        return None
    fit = fit_circle_2d(pts2d)
    if fit is None:
        return None
    cu, cv, radius, rel_rms = fit
    u_vals = [p[0] for p in pts2d]
    v_vals = [p[1] for p in pts2d]
    width = max(u_vals) - min(u_vals)
    height = max(v_vals) - min(v_vals)
    min_dim = max(min(width, height), 1.0e-9)
    max_dim = max(width, height)
    aspect = max_dim / min_dim
    cross_span = cross_section_span_for_axis(bb, axis_name) if bb is not None else max_dim
    radius_fraction = radius / max(cross_span, 1.0e-9)
    if radius < float(X1_R20B_CLUSTER_MIN_RADIUS):
        return None
    if radius_fraction > float(X1_R20B_CLUSTER_MAX_RADIUS_FRACTION):
        return None
    if rel_rms > float(X1_R20B_CLUSTER_MAX_REL_RMS):
        return None
    if aspect > float(X1_R20B_CLUSTER_MAX_ASPECT):
        return None

    # Avoid obvious outer-boundary fragments by rejecting centers/radii that touch
    # the projected side bounding box too strongly.
    umin, umax, vmin, vmax = r20b_cross_bounds(bb, axis_name)
    margin = max(radius * 0.32, cross_span * 0.015, 0.25)
    if cu - radius < umin - margin or cu + radius > umax + margin or cv - radius < vmin - margin or cv + radius > vmax + margin:
        return None

    shape_kind = "round_tessellated_opening"
    if aspect > 1.35:
        shape_kind = "oval_or_slot_tessellated_opening"
    center = r20b_point_from_axis_uv(axis_name, side_value, cu, cv)
    score = 0.0
    score += min(4.0, len(cluster) / 8.0)
    score += max(0.0, 2.0 - rel_rms * 8.0)
    score += max(0.0, 1.4 - abs(1.0 - aspect))
    return {
        "axis": axis_name,
        "side": side_name,
        "side_value": side_value,
        "center": center,
        "u": cu,
        "v": cv,
        "radius": radius,
        "diameter": 2.0 * radius,
        "width": width,
        "height": height,
        "aspect": aspect,
        "rel_rms": rel_rms,
        "points": len(cluster),
        "radius_fraction": radius_fraction,
        "kind": shape_kind,
        "score": score,
        "source": source_label,
    }


def r20b_collect_side_candidates(shape, bb, obj_label):
    all_candidates = []
    side_summary = []
    for axis_name in ("X", "Y", "Z"):
        mn, mx, axis_len = r20b_axis_bounds(bb, axis_name)
        for side_name, side_value in (("-", mn), ("+", mx)):
            points = r20b_collect_side_wall_points(shape, bb, axis_name, side_name)
            clusters = r20b_cluster_projected_points(points, axis_name, bb)
            cands = []
            for ci, cluster in enumerate(clusters, start=1):
                cand = r20b_candidate_from_cluster(
                    cluster, axis_name, side_name, bb, side_value,
                    "%s:%s%s_side_cluster_%03d" % (obj_label, side_name, axis_name, ci)
                )
                if cand is not None:
                    cands.append(cand)
            cands.sort(key=lambda c: (-float(c.get("score", 0.0)), -int(c.get("points", 0))))
            cands = cands[:int(X1_R20B_MAX_SIDE_CANDIDATES_PER_SIDE)]
            all_candidates.extend(cands)
            side_summary.append((axis_name, side_name, len(points), len(clusters), len(cands)))
    return all_candidates, side_summary


def r20b_cross_center_distance(a, b):
    return math.sqrt((float(a.get("u", 0.0)) - float(b.get("u", 0.0))) ** 2 + (float(a.get("v", 0.0)) - float(b.get("v", 0.0))) ** 2)


def r20b_pair_side_candidates(candidates, bb):
    pairs = []
    used = set()
    for axis_name in ("X", "Y", "Z"):
        minus = [(i, c) for i, c in enumerate(candidates) if c.get("axis") == axis_name and c.get("side") == "-"]
        plus = [(i, c) for i, c in enumerate(candidates) if c.get("axis") == axis_name and c.get("side") == "+"]
        for im, cm in minus:
            best = None
            for ip, cp in plus:
                if ip in used:
                    continue
                r1 = float(cm.get("radius", 0.0))
                r2 = float(cp.get("radius", 0.0))
                if r1 <= 0.0 or r2 <= 0.0:
                    continue
                rr = max(r1, r2) / max(min(r1, r2), 1.0e-9)
                if rr > float(X1_R20B_PAIR_RADIUS_RATIO_MAX):
                    continue
                dist = r20b_cross_center_distance(cm, cp)
                tol = max(float(X1_R20B_PAIR_CENTER_MIN), float(X1_R20B_PAIR_CENTER_FACTOR) * max(r1, r2))
                if dist > tol:
                    continue
                score = float(cm.get("score", 0.0)) + float(cp.get("score", 0.0)) + max(0.0, 2.0 - dist / max(tol, 1.0e-9))
                item = (score, dist, im, ip, cm, cp, rr)
                if best is None or item[0] > best[0]:
                    best = item
            if best is not None:
                _score, dist, im, ip, cm, cp, rr = best
                used.add(im)
                used.add(ip)
                rmin = min(float(cm.get("radius", 0.0)), float(cp.get("radius", 0.0)))
                rmax = max(float(cm.get("radius", 0.0)), float(cp.get("radius", 0.0)))
                kind = "paired_tessellated_bore_candidate"
                if rr > 1.12:
                    kind = "paired_tessellated_chamfer_or_body_candidate"
                start = cm.get("center")
                end = cp.get("center")
                if r20b_axis_coord(start, axis_name) > r20b_axis_coord(end, axis_name):
                    start, end = end, start
                pairs.append({
                    "axis": axis_name,
                    "minus": cm,
                    "plus": cp,
                    "start": start,
                    "end": end,
                    "radius": rmin,
                    "radius_min": rmin,
                    "radius_max": rmax,
                    "diameter": 2.0 * rmin,
                    "depth": abs(r20b_axis_coord(end, axis_name) - r20b_axis_coord(start, axis_name)),
                    "center_distance": dist,
                    "radius_ratio": rr,
                    "kind": kind,
                    "score": _score,
                    "used_indices": (im, ip),
                })
    pairs.sort(key=lambda p: -float(p.get("score", 0.0)))
    singles = [c for i, c in enumerate(candidates) if i not in used]
    singles.sort(key=lambda c: -float(c.get("score", 0.0)))
    return pairs, singles


def r20b_nearest_accepted_for_probe(axis_name, center, radius, accepted_primitives):
    best = None
    axis_vec = axis_vector(axis_name)
    for prim in accepted_primitives or []:
        try:
            if prim.get("axis_hint", "FREE") != axis_name:
                continue
            p_axis = prim.get("axis", axis_vec)
            if abs(v_dot(axis_vec, p_axis)) < X1_AXIS_PARALLEL_DOT:
                continue
            p_base = prim.get("base", prim.get("start", center))
            dist = line_distance_parallel(center, axis_vec, p_base, p_axis)
            pr = float(prim.get("radius", 0.0))
            rr = max(radius, pr) / max(min(radius, pr), 1.0e-9) if pr > 0.0 and radius > 0.0 else 999.0
            item = {"dist": dist, "radius": pr, "radius_ratio": rr, "profile": prim.get("profile", "BORE")}
            if best is None or item["dist"] < best["dist"]:
                best = item
        except Exception:
            continue
    return best


def r20b_probe_class(axis_name, center, radius, accepted_primitives):
    nearest = r20b_nearest_accepted_for_probe(axis_name, center, radius, accepted_primitives)
    if nearest is None:
        return "new_tessellated_diagnostic_candidate", 0.0, 0.0
    tol = max(float(X1_R20B_ACCEPTED_CENTER_MIN), float(X1_R20B_ACCEPTED_CENTER_FACTOR) * max(radius, nearest.get("radius", 0.0)))
    covered = nearest.get("dist", 999.0) <= tol and nearest.get("radius_ratio", 999.0) <= float(X1_R20B_ACCEPTED_RADIUS_FACTOR)
    if covered:
        return "already_covered_by_stable_bore", float(nearest.get("dist", 0.0)), float(nearest.get("radius", 0.0))
    return "new_tessellated_diagnostic_candidate", float(nearest.get("dist", 0.0)), float(nearest.get("radius", 0.0))


def r20b_set_marker_view(obj, color):
    try:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = int(X1_R20B_MARKER_TRANSPARENCY)
        obj.ViewObject.DisplayMode = "Shaded"
    except Exception:
        pass


def r20b_emit_pair_marker(doc, group, pair, index, source_obj, accepted_primitives):
    axis_name = pair.get("axis", "Z")
    radius = float(pair.get("radius", 0.0))
    start = pair.get("start")
    end = pair.get("end")
    if radius <= 0.0 or start is None or end is None:
        return None, "invalid"
    direction = v_sub(end, start)
    height = v_len(direction)
    if height <= 1.0e-9:
        return None, "invalid_height"
    center = v_add(start, v_scale(direction, 0.5))
    cls, nearest_dist, nearest_r = r20b_probe_class(axis_name, center, radius, accepted_primitives)
    try:
        obj = doc.addObject("Part::Feature", "X1_R20B_TessellatedPair_%03d" % index)
        obj.Shape = Part.makeCylinder(radius, height, start, v_unit(direction))
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = "X1 R20B DIAGNOSTIC tessellated pair %03d | %s | axis=%s | r=%.3f | h=%.3f" % (
            index, cls, axis_name, radius, height
        )
        color = (0.95, 0.15, 1.0)
        if cls == "already_covered_by_stable_bore":
            color = (0.35, 0.65, 1.0)
        elif "chamfer" in str(pair.get("kind", "")):
            color = (1.0, 0.62, 0.05)
        r20b_set_marker_view(obj, color)
        add_common_feature_metadata(obj, family="tessellated_axis_side_probe", role=cls, stage="R20B_axis_side_probe", kind="diagnostic", profile=pair.get("kind", "paired_tessellated_bore_candidate"))
        add_custom_text_property(obj, "X1_Axis", axis_name)
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_Diameter", "%.6f" % (2.0 * radius))
        add_custom_text_property(obj, "X1_Depth", "%.6f" % height)
        add_custom_text_property(obj, "X1_RadiusMin", "%.6f" % float(pair.get("radius_min", radius)))
        add_custom_text_property(obj, "X1_RadiusMax", "%.6f" % float(pair.get("radius_max", radius)))
        add_custom_text_property(obj, "X1_PairCenterDistance", "%.6f" % float(pair.get("center_distance", 0.0)))
        add_custom_text_property(obj, "X1_NearestAcceptedDistance", "%.6f" % nearest_dist)
        add_custom_text_property(obj, "X1_NearestAcceptedRadius", "%.6f" % nearest_r)
        add_custom_text_property(obj, "X1_PlacementCopied", str(copied))
        add_to_group(group, obj)
        x1_msg("  X1 R20B tessellated pair %03d: class=%s axis=%s kind=%s r=%.4f r_range=%.4f..%.4f depth=%.4f center_dist=%.4f nearest_r=%.4f" % (
            index, cls, axis_name, pair.get("kind", "?"), radius, float(pair.get("radius_min", radius)), float(pair.get("radius_max", radius)), height, float(pair.get("center_distance", 0.0)), nearest_r
        ))
        return obj, cls
    except Exception as exc:
        x1_warn("  X1 R20B tessellated pair marker %03d skipped: %s" % (index, exc))
        return None, "error"


def r20b_emit_single_marker(doc, group, cand, index, source_obj, accepted_primitives):
    axis_name = cand.get("axis", "Z")
    radius = float(cand.get("radius", 0.0))
    center = cand.get("center")
    if radius <= 0.0 or center is None:
        return None, "invalid"
    axis_vec = axis_vector(axis_name)
    side = str(cand.get("side", "+"))
    if side == "-":
        axis_vec = v_scale(axis_vec, -1.0)
    height = clamp(radius * float(X1_R20B_SINGLE_MARKER_HEIGHT_FACTOR), float(X1_R20B_SINGLE_MARKER_MIN_HEIGHT), float(X1_R20B_SINGLE_MARKER_MAX_HEIGHT))
    start = v_sub(center, v_scale(axis_vec, 0.5 * height))
    cls, nearest_dist, nearest_r = r20b_probe_class(axis_name, center, radius, accepted_primitives)
    try:
        obj = doc.addObject("Part::Feature", "X1_R20B_TessellatedSingle_%03d" % index)
        obj.Shape = Part.makeCylinder(radius, height, start, axis_vec)
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = "X1 R20B DIAGNOSTIC tessellated side %03d | %s | %s%s | r=%.3f" % (
            index, cls, cand.get("side", "+"), axis_name, radius
        )
        color = (0.65, 0.65, 0.65)
        if cls == "already_covered_by_stable_bore":
            color = (0.35, 0.65, 1.0)
        r20b_set_marker_view(obj, color)
        add_common_feature_metadata(obj, family="tessellated_axis_side_probe", role=cls, stage="R20B_axis_side_probe", kind="diagnostic", profile=cand.get("kind", "single_side_tessellated_opening_context"))
        add_custom_text_property(obj, "X1_Axis", axis_name)
        add_custom_text_property(obj, "X1_Side", cand.get("side", "?"))
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_RelRms", "%.6f" % float(cand.get("rel_rms", 0.0)))
        add_custom_text_property(obj, "X1_Aspect", "%.6f" % float(cand.get("aspect", 0.0)))
        add_custom_text_property(obj, "X1_PointCount", int(cand.get("points", 0)))
        add_custom_text_property(obj, "X1_NearestAcceptedDistance", "%.6f" % nearest_dist)
        add_custom_text_property(obj, "X1_NearestAcceptedRadius", "%.6f" % nearest_r)
        add_custom_text_property(obj, "X1_PlacementCopied", str(copied))
        add_to_group(group, obj)
        x1_msg("  X1 R20B tessellated single %03d: class=%s side=%s%s kind=%s r=%.4f pts=%d rel_rms=%.4f aspect=%.3f nearest_r=%.4f" % (
            index, cls, cand.get("side", "?"), axis_name, cand.get("kind", "?"), radius, int(cand.get("points", 0)), float(cand.get("rel_rms", 0.0)), float(cand.get("aspect", 0.0)), nearest_r
        ))
        return obj, cls
    except Exception as exc:
        x1_warn("  X1 R20B tessellated single marker %03d skipped: %s" % (index, exc))
        return None, "error"


def emit_tessellated_axis_side_probe_markers(doc, parent_group, obj, obj_index, accepted_primitives, bb):
    totals = defaultdict(int)
    if not bool(X1_R20B_ENABLE_TESSELLATED_AXIS_SIDE_PROBE):
        return totals
    if parent_group is None or bb is None:
        return totals
    label = getattr(obj, "Label", getattr(obj, "Name", "Object"))
    try:
        shape = obj.Shape
    except Exception:
        return totals

    x1_msg("  R20B tessellated axis-side probe: scanning +/-X, +/-Y, +/-Z diagnostic-only")
    try:
        candidates, side_summary = r20b_collect_side_candidates(shape, bb, label)
    except Exception as exc:
        x1_warn("  R20B tessellated axis-side probe failed during collection: %s" % exc)
        return totals

    for axis_name, side_name, point_count, cluster_count, cand_count in side_summary:
        if point_count or cand_count:
            x1_msg("    side %s%s: wall_points=%d clusters=%d candidates=%d" % (side_name, axis_name, point_count, cluster_count, cand_count))
    pairs, singles = r20b_pair_side_candidates(candidates, bb)
    totals["candidates"] = len(candidates)
    totals["pairs"] = len(pairs)
    # Keep raw candidate structures for R20B's consolidated ledger.  Integer
    # fields are still used for summary totals, and underscore fields are only
    # consumed inside this macro.
    totals["_side_candidates"] = candidates
    totals["_pairs"] = pairs
    totals["_singles"] = singles
    x1_msg("  R20B tessellated axis-side probe: candidates=%d paired=%d single_side=%d" % (len(candidates), len(pairs), len(singles)))

    pair_group = ensure_named_child_group(doc, parent_group, "R20B_Paired_Side_Candidates", "Paired Side Candidates")
    single_group = ensure_named_child_group(doc, parent_group, "R20B_Single_Side_Context", "Single-Side Context")

    for idx, pair in enumerate(pairs[:int(X1_R20B_MAX_PAIR_MARKERS)], start=1):
        obj_out, cls = r20b_emit_pair_marker(doc, pair_group, pair, idx, obj, accepted_primitives)
        if obj_out is not None:
            totals["pair_markers"] += 1
            if cls == "already_covered_by_stable_bore":
                totals["already_covered"] += 1
            elif cls == "new_tessellated_diagnostic_candidate":
                totals["new_candidates"] += 1

    for idx, cand in enumerate(singles[:int(X1_R20B_MAX_SINGLE_MARKERS)], start=1):
        obj_out, cls = r20b_emit_single_marker(doc, single_group, cand, idx, obj, accepted_primitives)
        if obj_out is not None:
            totals["single_markers"] += 1
            if cls == "already_covered_by_stable_bore":
                totals["already_covered"] += 1
            elif cls == "new_tessellated_diagnostic_candidate":
                totals["new_candidates"] += 1

    x1_msg("  R20B tessellated axis-side probe markers: pair=%d single=%d already_covered=%d new=%d" % (
        int(totals.get("pair_markers", 0)), int(totals.get("single_markers", 0)), int(totals.get("already_covered", 0)), int(totals.get("new_candidates", 0))
    ))
    return totals


# =============================================================================
# R20B consolidated tessellated evidence ledger
# =============================================================================


def r20b_obj_name_safe(text, max_len=52):
    safe = []
    for ch in str(text):
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        else:
            safe.append("_")
    out = "".join(safe).strip("_")
    return out[:max_len] or "entry"


def r20b_pair_center(pair):
    start = pair.get("start")
    end = pair.get("end")
    if start is None or end is None:
        return None
    return v_add(start, v_scale(v_sub(end, start), 0.5))


def r20b_ledger_entry_key(entry):
    return "%s|%.3f|%.3f|%.3f|%.3f" % (
        entry.get("axis", "?"),
        float(entry.get("center_u", 0.0)),
        float(entry.get("center_v", 0.0)),
        float(entry.get("radius", 0.0)),
        float(entry.get("depth", 0.0)),
    )


def r20b_cross_uv_for_center(center, axis_name):
    try:
        return r20b_cross_uv(center, axis_name)
    except Exception:
        return (0.0, 0.0)


def r20b_entry_from_accepted_primitive(prim, index):
    axis_name = str(prim.get("axis_hint", "FREE")).upper()
    if axis_name not in ("X", "Y", "Z"):
        return None
    center = prim.get("base", prim.get("start", None))
    if center is None:
        return None
    u, v = r20b_cross_uv_for_center(center, axis_name)
    start = prim.get("start", center)
    end = prim.get("end", center)
    depth = v_dist(start, end)
    radius = float(prim.get("radius", 0.0))
    return {
        "axis": axis_name,
        "center": center,
        "center_u": u,
        "center_v": v,
        "radius": radius,
        "radius_min": radius,
        "radius_max": radius,
        "depth": depth,
        "start": start,
        "end": end,
        "source_kind": "accepted_primitive",
        "classification": "stable_covered",
        "evidence_score": X1_R20B_ACCEPTED_WEIGHT,
        "evidence_count": 1,
        "evidence_sources": ["accepted_bore_%03d" % index],
        "profiles": [str(prim.get("profile", "BORE"))],
        "accepted_radius": radius,
        "suppress_marker": True,
    }


def r20b_entry_from_fast_stack(stack, accepted_primitives):
    try:
        cls, reason, nearest = r20b_classify_stack(stack, accepted_primitives)
        axis = str(stack.get("axis", "Z")).upper()
        axial_mid = 0.5 * (float(stack.get("axial_min", 0.0)) + float(stack.get("axial_max", 0.0)))
        center = point_from_cross_axis(stack.get("cross", (0.0, 0.0)), axial_mid, axis)
        u, v = r20b_cross_uv_for_center(center, axis)
        radius = r20b_stack_marker_radius(stack, cls)
        axial_min = float(stack.get("axial_min", axial_mid))
        axial_max = float(stack.get("axial_max", axial_mid))
        start = point_from_cross_axis(stack.get("cross", (0.0, 0.0)), axial_min, axis)
        end = point_from_cross_axis(stack.get("cross", (0.0, 0.0)), axial_max, axis)
        score = X1_R20B_FAST_STACK_WEIGHT
        score += 0.50 * int(stack.get("e074_confirmed_members", 0))
        score += 0.35 * int(stack.get("inner_members", 0))
        if cls in ("missing_bore_with_chamfer_candidate", "chamfer_mouth_with_smaller_body_candidate"):
            score += 2.0
        elif cls == "already_covered_by_stable_bore":
            score += 1.0
        accepted_radius = 0.0
        if nearest is not None:
            accepted_radius = float(nearest.get("primitive_radius", 0.0))
        return {
            "axis": axis,
            "center": center,
            "center_u": u,
            "center_v": v,
            "radius": float(radius),
            "radius_min": float(stack.get("radius_min", radius)),
            "radius_max": float(stack.get("radius_max", radius)),
            "depth": abs(axial_max - axial_min),
            "start": start,
            "end": end,
            "source_kind": "fast_stack",
            "classification": cls,
            "reason": reason,
            "evidence_score": score,
            "evidence_count": int(stack.get("member_count", 1)),
            "evidence_sources": ["FAST:%s" % compact_source_name(stack.get("sources", "stack"), 180)],
            "profiles": [str(stack.get("stack_kind", "layer_stack"))],
            "accepted_radius": accepted_radius,
            "nearest_accepted_radius": accepted_radius,
            "radius_delta_ratio": float(stack.get("radius_delta_ratio", 0.0)),
            "radius_range_ratio": float(stack.get("radius_range_ratio", 0.0)),
            "suppress_marker": bool(
                X1_R20B_SUPPRESS_FAST_ONLY_TESSELLATION_ONLY_UNANCHORED
                and cls == "tessellation_only_unanchored"
                and score <= float(X1_R20B_UNANCHORED_FAST_ONLY_MAX_EVIDENCE)
            ),
        }
    except Exception:
        return None


def r20b_entry_from_side_pair(pair, accepted_primitives):
    try:
        axis = str(pair.get("axis", "Z")).upper()
        center = r20b_pair_center(pair)
        if center is None:
            return None
        radius = float(pair.get("radius", 0.0))
        cls, nearest_dist, nearest_r = r20b_probe_class(axis, center, radius, accepted_primitives)
        classification = "tessellated_bore_candidate"
        if cls == "already_covered_by_stable_bore":
            classification = "stable_covered"
        elif "chamfer" in str(pair.get("kind", "")):
            classification = "tessellated_chamfer_body_candidate"
        score = X1_R20B_SIDE_PAIR_WEIGHT + float(pair.get("score", 0.0))
        if classification == "tessellated_chamfer_body_candidate":
            score += 1.25
        u, v = r20b_cross_uv_for_center(center, axis)
        return {
            "axis": axis,
            "center": center,
            "center_u": u,
            "center_v": v,
            "radius": radius,
            "radius_min": float(pair.get("radius_min", radius)),
            "radius_max": float(pair.get("radius_max", radius)),
            "depth": float(pair.get("depth", 0.0)),
            "start": pair.get("start"),
            "end": pair.get("end"),
            "source_kind": "side_pair",
            "classification": classification,
            "evidence_score": score,
            "evidence_count": 2,
            "evidence_sources": ["side_pair:%s" % str(pair.get("kind", "pair"))],
            "profiles": [str(pair.get("kind", "paired_tessellated_bore_candidate"))],
            "nearest_accepted_distance": nearest_dist,
            "nearest_accepted_radius": nearest_r,
            "pair_center_distance": float(pair.get("center_distance", 0.0)),
        }
    except Exception:
        return None


def r20b_entry_from_side_single(cand, accepted_primitives):
    try:
        axis = str(cand.get("axis", "Z")).upper()
        center = cand.get("center")
        if center is None:
            return None
        radius = float(cand.get("radius", 0.0))
        cls, nearest_dist, nearest_r = r20b_probe_class(axis, center, radius, accepted_primitives)
        classification = "weak_single_side_context"
        suppress = False
        if cls == "already_covered_by_stable_bore":
            classification = "suppressed_near_accepted"
            suppress = bool(X1_R20B_SINGLE_SUPPRESS_NEAR_ACCEPTED)
        elif float(cand.get("score", 0.0)) < float(X1_R20B_SINGLE_WEAK_MIN_SCORE):
            classification = "weak_single_side_context"
            suppress = True
        elif nearest_r > X1_MIN_RADIUS:
            center_limit = max(float(X1_R20B_SINGLE_NEAR_ACCEPTED_CENTER_FACTOR) * max(radius, nearest_r), X1_R20B_ACCEPTED_CENTER_MIN)
            radius_ratio = max(radius, nearest_r) / max(min(radius, nearest_r), 1.0e-9)
            if nearest_dist <= center_limit and radius_ratio <= float(X1_R20B_SINGLE_NEAR_ACCEPTED_RADIUS_FACTOR):
                classification = "suppressed_near_accepted"
                suppress = bool(X1_R20B_SINGLE_SUPPRESS_NEAR_ACCEPTED)
        u, v = r20b_cross_uv_for_center(center, axis)
        axis_vec = axis_vector(axis)
        side = str(cand.get("side", "+"))
        if side == "-":
            axis_vec = v_scale(axis_vec, -1.0)
        height = clamp(radius * float(X1_R20B_SINGLE_MARKER_HEIGHT_FACTOR), float(X1_R20B_SINGLE_MARKER_MIN_HEIGHT), float(X1_R20B_SINGLE_MARKER_MAX_HEIGHT))
        start = v_sub(center, v_scale(axis_vec, 0.5 * height))
        end = v_add(center, v_scale(axis_vec, 0.5 * height))
        return {
            "axis": axis,
            "center": center,
            "center_u": u,
            "center_v": v,
            "radius": radius,
            "radius_min": radius,
            "radius_max": radius,
            "depth": height,
            "start": start,
            "end": end,
            "source_kind": "side_single",
            "classification": classification,
            "evidence_score": X1_R20B_SIDE_SINGLE_WEIGHT + float(cand.get("score", 0.0)),
            "evidence_count": 1,
            "evidence_sources": ["single:%s%s:%s" % (side, axis, compact_source_name(cand.get("source", "side"), 120))],
            "profiles": [str(cand.get("kind", "single_side_tessellated_opening_context"))],
            "nearest_accepted_distance": nearest_dist,
            "nearest_accepted_radius": nearest_r,
            "rel_rms": float(cand.get("rel_rms", 0.0)),
            "aspect": float(cand.get("aspect", 0.0)),
            "point_count": int(cand.get("points", 0)),
            "suppress_marker": suppress,
        }
    except Exception:
        return None


def r20b_entries_compatible(a, b):
    if str(a.get("axis", "?")) != str(b.get("axis", "?")):
        return False
    ra = max(float(a.get("radius", 0.0)), X1_MIN_RADIUS)
    rb = max(float(b.get("radius", 0.0)), X1_MIN_RADIUS)
    ratio = max(ra, rb) / max(min(ra, rb), 1.0e-9)
    if ratio > float(X1_R20B_CONSOLIDATE_RADIUS_RATIO_MAX):
        return False
    du = float(a.get("center_u", 0.0)) - float(b.get("center_u", 0.0))
    dv = float(a.get("center_v", 0.0)) - float(b.get("center_v", 0.0))
    dist = math.sqrt(du * du + dv * dv)
    tol = max(float(X1_R20B_CONSOLIDATE_CENTER_MIN), float(X1_R20B_CONSOLIDATE_CENTER_RADIUS_FACTOR) * max(ra, rb))
    return dist <= tol


def r20b_merge_entry_group(entries):
    if not entries:
        return None
    weights = [max(0.25, float(e.get("evidence_score", 1.0))) for e in entries]
    total_w = sum(weights)
    axis = entries[0].get("axis", "Z")
    cx = sum(float(e.get("center", v_new(0, 0, 0)).x) * w for e, w in zip(entries, weights)) / max(total_w, 1.0e-9)
    cy = sum(float(e.get("center", v_new(0, 0, 0)).y) * w for e, w in zip(entries, weights)) / max(total_w, 1.0e-9)
    cz = sum(float(e.get("center", v_new(0, 0, 0)).z) * w for e, w in zip(entries, weights)) / max(total_w, 1.0e-9)
    center = v_new(cx, cy, cz)
    radius = median([float(e.get("radius", 0.0)) for e in entries if float(e.get("radius", 0.0)) > 0.0])
    radius_min = min(float(e.get("radius_min", e.get("radius", radius))) for e in entries)
    radius_max = max(float(e.get("radius_max", e.get("radius", radius))) for e in entries)
    depth = max(float(e.get("depth", 0.0)) for e in entries)
    sources = []
    profiles = []
    classes = []
    source_kinds = []
    suppressed = False
    for e in entries:
        sources.extend(list(e.get("evidence_sources", [])))
        profiles.extend(list(e.get("profiles", [])))
        classes.append(str(e.get("classification", "")))
        source_kinds.append(str(e.get("source_kind", "")))
        suppressed = suppressed or bool(e.get("suppress_marker", False))
    priority = [
        "stable_covered",
        "accepted_bore_may_be_chamfer_mouth_or_mixed_radius",
        "chamfer_mouth_with_smaller_body_candidate",
        "missing_bore_with_chamfer_candidate",
        "missing_feature_candidate",
        "tessellated_chamfer_body_candidate",
        "tessellated_bore_candidate",
        "weak_single_side_context",
        "suppressed_near_accepted",
        "tessellation_only_unanchored",
    ]
    final_class = "tessellated_bore_candidate"
    for p in priority:
        if p in classes:
            final_class = p
            break
    if final_class == "stable_covered" and any(c in classes for c in ("accepted_bore_may_be_chamfer_mouth_or_mixed_radius", "chamfer_mouth_with_smaller_body_candidate")):
        final_class = "stable_radius_may_be_chamfer_mouth"
    if final_class == "missing_feature_candidate" and "tessellated_chamfer_body_candidate" in classes:
        final_class = "missing_bore_with_chamfer_candidate"
    if final_class.startswith("suppressed") or final_class == "weak_single_side_context":
        suppressed = True
    if final_class == "tessellation_only_unanchored":
        # R20B: unanchored FAST-only tessellation signals are retained in the
        # ledger but are not drawn as cylinders. They do not have independent
        # side-pair/accepted support and were confirmed as a false-positive
        # visual marker on the reference runs.
        if set(source_kinds).issubset({"fast_stack"}):
            suppressed = True

    if (
        final_class == "tessellated_bore_candidate"
        and bool(X1_R20B_SUPPRESS_SIDE_PAIR_ONLY_MARKERS)
        and set(source_kinds).issubset({"side_pair"})
    ):
        # R20B: pure side-pair evidence is valuable, especially on Mesh025-like
        # hard tessellated imports, but it is not promoted visually by default.
        # Keep it in the ledger as context until another system confirms it.
        final_class = "side_pair_context_only"
        suppressed = True
        try:
            if depth / max(float(radius), 1.0e-9) >= float(X1_R20B_SIDE_PAIR_CONTEXT_MAX_DEPTH_RADIUS_RATIO):
                final_class = "side_pair_context_high_depth_ratio"
        except Exception:
            pass
    start = entries[0].get("start")
    end = entries[0].get("end")
    if start is None or end is None or v_dist(start, end) <= 1.0e-9:
        axis_vec = axis_vector(axis)
        start = v_sub(center, v_scale(axis_vec, max(depth, radius) * 0.5))
        end = v_add(center, v_scale(axis_vec, max(depth, radius) * 0.5))
    return {
        "axis": axis,
        "center": center,
        "center_u": r20b_cross_uv_for_center(center, axis)[0],
        "center_v": r20b_cross_uv_for_center(center, axis)[1],
        "radius": max(float(radius), X1_MIN_RADIUS),
        "radius_min": radius_min,
        "radius_max": radius_max,
        "depth": depth,
        "start": start,
        "end": end,
        "classification": final_class,
        "evidence_score": sum(float(e.get("evidence_score", 0.0)) for e in entries),
        "evidence_count": sum(int(e.get("evidence_count", 1)) for e in entries),
        "source_kinds": sorted(set(source_kinds)),
        "profiles": sorted(set(profiles)),
        "evidence_sources": sorted(set(sources))[:12],
        "merged_count": len(entries),
        "suppress_marker": suppressed,
        "classes": sorted(set(classes)),
    }


def r20b_consolidate_entries(entries):
    groups = []
    for entry in sorted(entries, key=lambda e: -float(e.get("evidence_score", 0.0))):
        placed = False
        for group in groups:
            if any(r20b_entries_compatible(entry, existing) for existing in group):
                group.append(entry)
                placed = True
                break
        if not placed:
            groups.append([entry])
    merged = []
    for group in groups:
        item = r20b_merge_entry_group(group)
        if item is not None:
            merged.append(item)
    merged.sort(key=lambda e: (bool(e.get("suppress_marker", False)), -float(e.get("evidence_score", 0.0)), str(e.get("axis", ""))))
    return merged


def r20b_consolidated_group_for_class(doc, parent, classification):
    if classification in ("stable_covered", "stable_radius_may_be_chamfer_mouth"):
        return ensure_named_child_group(doc, parent, "01_Stable_Covered_And_Mouth_Checks", "01 Stable Covered / Mouth Checks")
    if classification in ("missing_bore_with_chamfer_candidate", "missing_feature_candidate"):
        return ensure_named_child_group(doc, parent, "02_Missing_Feature_Candidates", "02 Missing Feature Candidates")
    if classification in ("chamfer_mouth_with_smaller_body_candidate", "tessellated_chamfer_body_candidate", "accepted_bore_may_be_chamfer_mouth_or_mixed_radius"):
        return ensure_named_child_group(doc, parent, "03_Chamfer_Body_Candidates", "03 Chamfer / Body Candidates")
    if classification in ("weak_single_side_context", "suppressed_near_accepted", "tessellation_only_unanchored", "side_pair_context_only", "side_pair_context_high_depth_ratio"):
        return ensure_named_child_group(doc, parent, "04_Suppressed_Weak_Context", "04 Suppressed / Weak Context")
    return ensure_named_child_group(doc, parent, "05_Other_Tessellated_Candidates", "05 Other Tessellated Candidates")


def r20b_marker_color_for_class(classification):
    if classification in ("stable_covered", "stable_radius_may_be_chamfer_mouth"):
        return (0.35, 0.65, 1.0)
    if classification in ("missing_bore_with_chamfer_candidate", "missing_feature_candidate"):
        return (1.0, 0.20, 0.20)
    if classification in ("chamfer_mouth_with_smaller_body_candidate", "tessellated_chamfer_body_candidate", "accepted_bore_may_be_chamfer_mouth_or_mixed_radius"):
        return (1.0, 0.62, 0.05)
    if classification in ("weak_single_side_context", "suppressed_near_accepted", "tessellation_only_unanchored", "side_pair_context_only", "side_pair_context_high_depth_ratio"):
        return (0.55, 0.55, 0.55)
    return (0.95, 0.15, 1.0)


def r20b_review_suppression_reason(entry):
    """Human-readable reason why a paired/context ledger entry is not accepted.

    R20B uses this only for diagnostics and structured export.  It does not
    alter accepted primitives, cylinder emission, or the conservative ledger
    classification.
    """
    reasons = []
    cls = str(entry.get("classification", ""))
    source_kinds = set(str(v) for v in entry.get("source_kinds", []))
    radius = max(float(entry.get("radius", 0.0)), 1.0e-9)
    depth = float(entry.get("depth", 0.0))
    if bool(entry.get("suppress_marker", False)):
        reasons.append("ledger_suppressed_visual_promotion")
    if cls == "side_pair_context_only":
        reasons.append("side_pair_context_only")
    if cls == "side_pair_context_high_depth_ratio":
        reasons.append("side_pair_context_high_depth_ratio")
    if source_kinds.issubset({"side_pair"}):
        reasons.append("only_opposing_side_pair_evidence")
    if "side_pair" in source_kinds and "fast_stack" not in source_kinds and "accepted_primitive" not in source_kinds:
        reasons.append("no_fast_stack_or_accepted_anchor")
    if "accepted_primitive" in source_kinds:
        reasons.append("accepted_path_already_owns_geometry")
    if "side_single" in source_kinds and "side_pair" not in source_kinds:
        reasons.append("single_side_only")
    if depth / radius >= float(X1_R20B_SIDE_PAIR_CONTEXT_MAX_DEPTH_RADIUS_RATIO):
        reasons.append("high_depth_radius_ratio")
    if cls == "tessellation_only_unanchored":
        reasons.append("tessellation_only_unanchored")
    if not reasons:
        reasons.append("not_promoted_by_r20b_review_policy")
    return "+".join(sorted(set(reasons)))


def r20b_review_tier_for_entry(entry):
    """Return 'A', 'B', or None for diagnostic-only review marker emission."""
    if not bool(X1_R20B_EMIT_TESSELLATED_REVIEW_MARKERS):
        return None
    cls = str(entry.get("classification", ""))
    source_kinds = set(str(v) for v in entry.get("source_kinds", []))
    required = str(X1_R20B_REVIEW_MARKER_REQUIRED_SOURCE_KIND)
    if required not in source_kinds:
        return None
    # Stable accepted features remain owned by the accepted-bore path.
    if "accepted_primitive" in source_kinds:
        return None
    evidence = float(entry.get("evidence_score", 0.0))
    if cls in tuple(X1_R20B_REVIEW_TIER_A_CLASSES) and not bool(entry.get("suppress_marker", False)):
        if evidence >= float(X1_R20B_REVIEW_TIER_A_MIN_EVIDENCE):
            return "A"
    # Tier B deliberately permits suppressed/context entries.  It is for review
    # of the strong paired candidates that R19B kept in the ledger but did not
    # draw, e.g. Mesh025's four additional side-pair context rings.
    if cls in tuple(X1_R20B_REVIEW_TIER_B_CLASSES):
        if evidence >= float(X1_R20B_REVIEW_TIER_B_MIN_EVIDENCE):
            return "B"
    return None


def r20b_should_emit_tessellated_review_marker(entry):
    return r20b_review_tier_for_entry(entry) is not None


def r20b_tessellated_review_group(doc, parent_group, tier="A"):
    if str(tier).upper() == "B":
        return ensure_named_child_group(
            doc,
            parent_group,
            "06B_Tessellated_Context_Review_Markers",
            "06B Tessellated Context Review Markers - Diagnostic Only",
        )
    return ensure_named_child_group(
        doc,
        parent_group,
        "06A_Tessellated_Strong_Review_Markers",
        "06A Tessellated Strong Review Markers - Diagnostic Only",
    )


def r20b_review_label_for_tier(tier):
    if str(tier).upper() == "B":
        return X1_R20B_REVIEW_TIER_B_LABEL
    return X1_R20B_REVIEW_TIER_A_LABEL


def r20b_review_color_for_tier(tier):
    if str(tier).upper() == "B":
        return (0.45, 0.45, 0.95)
    return (1.0, 0.35, 0.0)


def r20b_review_transparency_for_tier(tier):
    if str(tier).upper() == "B":
        return int(X1_R20B_REVIEW_MARKER_TIER_B_TRANSPARENCY)
    return int(X1_R20B_REVIEW_MARKER_TIER_A_TRANSPARENCY)


def r20b_emit_tessellated_review_marker(doc, parent_group, entry, index, source_obj):
    tier = r20b_review_tier_for_entry(entry)
    if tier is None:
        return None
    radius = float(entry.get("radius", 0.0))
    start = entry.get("start")
    end = entry.get("end")
    if radius <= X1_MIN_RADIUS or start is None or end is None:
        return None
    direction = v_sub(end, start)
    height = v_len(direction)
    if height <= 1.0e-9:
        axis_vec = axis_vector(entry.get("axis", "Z"))
        height = max(radius, float(entry.get("depth", radius)))
        center = entry.get("center", v_new(0, 0, 0))
        start = v_sub(center, v_scale(axis_vec, 0.5 * height))
        direction = axis_vec
    cls = str(entry.get("classification", "tessellated_chamfer_body_candidate"))
    group = r20b_tessellated_review_group(doc, parent_group, tier)
    label = r20b_review_label_for_tier(tier)
    suppression_reason = r20b_review_suppression_reason(entry)
    try:
        obj = doc.addObject("Part::Feature", "X1_R20B_TessellatedReview_%s_%03d" % (tier, index))
        obj.Shape = Part.makeCylinder(radius, height, start, v_unit(direction))
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = (
            "X1 R20B REVIEW TIER %s %03d | %s | class=%s | axis=%s | r=%.3f | depth=%.3f | evidence=%.2f"
            % (
                tier,
                index,
                label,
                cls,
                entry.get("axis", "?"),
                radius,
                height,
                float(entry.get("evidence_score", 0.0)),
            )
        )
        try:
            obj.ViewObject.ShapeColor = r20b_review_color_for_tier(tier)
            obj.ViewObject.Transparency = r20b_review_transparency_for_tier(tier)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_common_feature_metadata(
            obj,
            family="tessellated_review_marker",
            role="not_accepted_tessellated_review_tier_%s" % tier,
            stage="R20B_tessellated_review_tier_%s" % tier,
            kind="diagnostic_review_only",
            profile=",".join(entry.get("profiles", [])[:4]),
        )
        add_custom_text_property(obj, "X1_Decision", "review_only_not_accepted")
        add_custom_text_property(obj, "X1_ReviewTier", tier)
        add_custom_text_property(obj, "X1_ReviewPolicy", label)
        add_custom_text_property(obj, "X1_SuppressionReason", suppression_reason)
        add_custom_text_property(obj, "X1_Axis", entry.get("axis", "?"))
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_RadiusMin", "%.6f" % float(entry.get("radius_min", radius)))
        add_custom_text_property(obj, "X1_RadiusMax", "%.6f" % float(entry.get("radius_max", radius)))
        add_custom_text_property(obj, "X1_Depth", "%.6f" % float(height))
        add_custom_text_property(obj, "X1_EvidenceScore", "%.6f" % float(entry.get("evidence_score", 0.0)))
        add_custom_text_property(obj, "X1_EvidenceCount", int(entry.get("evidence_count", 0)))
        add_custom_text_property(obj, "X1_SourceKinds", ",".join(entry.get("source_kinds", [])))
        add_custom_text_property(obj, "X1_SourceClasses", ",".join(entry.get("classes", [])))
        add_custom_text_property(obj, "X1_EvidenceSources", " | ".join(entry.get("evidence_sources", [])[:6]))
        add_custom_text_property(obj, "X1_AcceptedFeature", "False")
        add_custom_text_property(obj, "X1_PlacementCopied", str(copied))
        add_to_group(group, obj)
        x1_msg(
            "    X1 R20B tessellated review marker %s-%03d: %s axis=%s r=%.4f depth=%.4f evidence=%.2f accepted=False reason=%s"
            % (
                tier,
                index,
                cls,
                entry.get("axis", "?"),
                radius,
                height,
                float(entry.get("evidence_score", 0.0)),
                suppression_reason,
            )
        )
        return obj
    except Exception as exc:
        x1_warn("  X1 R20B tessellated review marker %s-%03d skipped: %s" % (tier, index, exc))
        return None


def r20b_is_promotion_preview_allowed(entry):
    """Return (allowed, reason) for R20B preview-only promotion cylinders.

    This is deliberately not an accepted-bore promotion gate.  It only decides
    whether a consolidated ledger entry deserves a separate visual preview
    cylinder.  The stable accepted primitive path and emitted cylinder count are
    untouched.
    """
    if not bool(X1_R20B_EMIT_PROMOTION_PREVIEW_CYLINDERS):
        return False, "promotion_preview_disabled"
    review_tier = str(r20b_review_tier_for_entry(entry) or "").upper()
    cls = str(entry.get("classification", "") or "")
    source_kinds = set(str(v) for v in entry.get("source_kinds", []))
    reason = str(entry.get("reason", "") or "") + "+" + r20b_review_suppression_reason(entry)

    try:
        radius = float(entry.get("radius", 0.0) or 0.0)
        depth = float(entry.get("depth", 0.0) or 0.0)
    except Exception:
        return False, "invalid_radius_or_depth"

    if review_tier != "A":
        return False, "not_tier_a"
    if cls not in tuple(X1_R20B_PROMOTION_PREVIEW_CLASSES):
        return False, "class_not_promotable"
    if "side_pair" not in source_kinds:
        return False, "missing_side_pair_evidence"
    if radius <= 0.0 or depth <= 0.0:
        return False, "non_positive_radius_or_depth"
    if depth <= radius * float(X1_R20B_PROMOTION_PREVIEW_MIN_DEPTH_RADIUS_RATIO):
        return False, "depth_radius_ratio_too_low"

    blocked_classes = {
        "stable_covered",
        "stable_radius_may_be_chamfer_mouth",
        "side_pair_context_only",
        "side_pair_context_high_depth_ratio",
        "weak_single_side_context",
        "suppressed_near_accepted",
        "tessellation_only_unanchored",
    }
    if cls in blocked_classes:
        return False, "blocked_context_or_stable_class"
    if "single_side_only" in reason:
        return False, "single_side_only"
    if "tessellation_only_unanchored" in reason:
        return False, "unanchored_tessellation_only"
    if "accepted_path_already_owns_geometry" in reason:
        return False, "already_owned_by_accepted_path"

    return True, "tier_a_side_pair_body_candidate_not_in_stable_path"


def r20b_promotion_preview_group(doc, parent_group):
    return ensure_named_child_group(
        doc,
        parent_group,
        "06C_Tessellated_Promotion_Preview_Cylinders",
        "06C Tessellated Promotion Preview Cylinders - Preview Only",
    )


def r20b_emit_promotion_preview_cylinder(doc, parent_group, entry, index, source_obj):
    allowed, preview_reason = r20b_is_promotion_preview_allowed(entry)
    if not allowed:
        return None
    radius = float(entry.get("radius", 0.0) or 0.0)
    start = entry.get("start")
    end = entry.get("end")
    if radius <= X1_MIN_RADIUS:
        return None
    if start is None or end is None or v_dist(start, end) <= 1.0e-9:
        axis_vec = axis_vector(entry.get("axis", "Z"))
        center = entry.get("center", v_new(0, 0, 0))
        height = max(radius, float(entry.get("depth", radius) or radius))
        start = v_sub(center, v_scale(axis_vec, 0.5 * height))
        end = v_add(center, v_scale(axis_vec, 0.5 * height))
    direction = v_sub(end, start)
    height = v_len(direction)
    if height <= 1.0e-9:
        return None
    cls = str(entry.get("classification", "tessellated_promotion_preview"))
    group = r20b_promotion_preview_group(doc, parent_group)
    try:
        obj = doc.addObject("Part::Feature", "X1_R20B_PromotionPreview_%03d" % index)
        obj.Shape = Part.makeCylinder(radius, height, start, v_unit(direction))
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = (
            "X1 R20B promotion-preview cylinder %03d | PREVIEW_ONLY | NOT_ACCEPTED | class=%s | axis=%s | r=%.3f | depth=%.3f | evidence=%.2f"
            % (
                index,
                cls,
                entry.get("axis", "?"),
                radius,
                height,
                float(entry.get("evidence_score", 0.0)),
            )
        )
        try:
            obj.ViewObject.ShapeColor = X1_R20B_PROMOTION_PREVIEW_COLOR
            obj.ViewObject.Transparency = int(X1_R20B_PROMOTION_PREVIEW_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_common_feature_metadata(
            obj,
            family="tessellated_promotion_preview",
            role="preview_only_not_accepted",
            stage="R20B_guarded_tessellated_promotion_preview",
            kind="diagnostic_preview_only",
            profile=",".join(entry.get("profiles", [])[:4]),
        )
        add_custom_text_property(obj, "X1_Decision", "promotion_preview_only_not_accepted")
        add_custom_text_property(obj, "X1_PromotionState", "preview_only")
        add_custom_text_property(obj, "X1_PromotionReason", preview_reason)
        add_custom_text_property(obj, "X1_ReviewTier", "A")
        add_custom_text_property(obj, "X1_ReviewPolicy", X1_R20B_PROMOTION_PREVIEW_LABEL)
        add_custom_text_property(obj, "X1_AcceptedFeature", "False")
        add_custom_text_property(obj, "X1_AcceptedPathPromotion", "False")
        add_custom_text_property(obj, "X1_Axis", entry.get("axis", "?"))
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_RadiusMin", "%.6f" % float(entry.get("radius_min", radius)))
        add_custom_text_property(obj, "X1_RadiusMax", "%.6f" % float(entry.get("radius_max", radius)))
        add_custom_text_property(obj, "X1_Depth", "%.6f" % float(height))
        add_custom_text_property(obj, "X1_EvidenceScore", "%.6f" % float(entry.get("evidence_score", 0.0)))
        add_custom_text_property(obj, "X1_EvidenceCount", int(entry.get("evidence_count", 0)))
        add_custom_text_property(obj, "X1_SourceKinds", ",".join(entry.get("source_kinds", [])))
        add_custom_text_property(obj, "X1_SourceClasses", ",".join(entry.get("classes", [])))
        add_custom_text_property(obj, "X1_EvidenceSources", " | ".join(entry.get("evidence_sources", [])[:6]))
        add_custom_text_property(obj, "X1_PlacementCopied", str(copied))
        add_to_group(group, obj)
        x1_msg(
            "    X1 R20B promotion-preview cylinder %03d: class=tessellated_promotion_preview source_class=%s axis=%s radius=%.4f depth=%.4f evidence=%.2f accepted=False promotion_state=preview_only reason=%s"
            % (
                index,
                cls,
                entry.get("axis", "?"),
                radius,
                height,
                float(entry.get("evidence_score", 0.0)),
                preview_reason,
            )
        )
        return obj
    except Exception as exc:
        x1_warn("  X1 R20B promotion-preview cylinder %03d skipped: %s" % (index, exc))
        return None

def r20b_is_accepted_promotion_allowed(entry):
    """Return (allowed, reason) for R20B accepted-path missing-bore promotion.

    The gate is deliberately narrow. It restores the two Mesh008 missing bores
    where the conservative ledger has both FAST layer-stack evidence and
    opposing side-pair tessellated evidence. It blocks side-pair-only Mesh025
    review candidates and FAST-only weak missing-feature candidates.
    """
    if not bool(X1_R20B_ENABLE_GUARDED_MISSING_BORE_PROMOTION):
        return False, "accepted_promotion_disabled"
    cls = str(entry.get("classification", "") or "")
    source_kinds = set(str(v) for v in entry.get("source_kinds", []))
    required = set(str(v) for v in X1_R20B_ACCEPTED_PROMOTION_REQUIRED_SOURCE_KINDS)
    reason = str(entry.get("reason", "") or "") + "+" + r20b_review_suppression_reason(entry)

    try:
        radius = float(entry.get("radius", 0.0) or 0.0)
        radius_min = float(entry.get("radius_min", radius) or radius)
        radius_max = float(entry.get("radius_max", radius) or radius)
        depth = float(entry.get("depth", 0.0) or 0.0)
        evidence = float(entry.get("evidence_score", 0.0) or 0.0)
    except Exception:
        return False, "invalid_radius_depth_or_evidence"

    if cls not in tuple(X1_R20B_ACCEPTED_PROMOTION_CLASSES):
        return False, "class_not_accepted_promotable"
    if not required.issubset(source_kinds):
        return False, "missing_required_fast_stack_or_side_pair_evidence"
    if bool(entry.get("suppress_marker", False)):
        return False, "suppressed_ledger_entry"
    if evidence < float(X1_R20B_ACCEPTED_PROMOTION_MIN_EVIDENCE):
        return False, "evidence_below_accepted_promotion_floor"
    if radius <= X1_MIN_RADIUS or depth <= X1_MIN_DEPTH:
        return False, "radius_or_depth_too_small"
    if depth <= radius * float(X1_R20B_ACCEPTED_PROMOTION_MIN_DEPTH_RADIUS_RATIO):
        return False, "depth_radius_ratio_too_low"
    rr = max(radius_max, radius) / max(min(radius_min, radius), 1.0e-9)
    if rr > float(X1_R20B_ACCEPTED_PROMOTION_MAX_RADIUS_RATIO):
        return False, "radius_range_ratio_too_wide"
    if "single_side_only" in reason:
        return False, "single_side_only"
    if "tessellation_only_unanchored" in reason:
        return False, "unanchored_tessellation_only"
    if "accepted_path_already_owns_geometry" in reason:
        return False, "already_owned_by_accepted_path"

    return True, "fast_stack_plus_side_pair_missing_bore_with_chamfer_promoted"


def r20b_accepted_promotion_group(doc, parent_group):
    return ensure_named_child_group(
        doc,
        parent_group,
        "02B_Guarded_Missing_Bore_Promotions",
        "02B Guarded Missing Bore Promotions - Accepted",
    )


def r20b_emit_accepted_promotion_cylinder(doc, parent_group, entry, index, source_obj):
    allowed, promote_reason = r20b_is_accepted_promotion_allowed(entry)
    if not allowed:
        return None
    radius = float(entry.get("radius", 0.0) or 0.0)
    start = entry.get("start")
    end = entry.get("end")
    if radius <= X1_MIN_RADIUS:
        return None
    if start is None or end is None or v_dist(start, end) <= 1.0e-9:
        axis_vec = axis_vector(entry.get("axis", "Z"))
        center = entry.get("center", v_new(0, 0, 0))
        height = max(radius, float(entry.get("depth", radius) or radius))
        start = v_sub(center, v_scale(axis_vec, 0.5 * height))
        end = v_add(center, v_scale(axis_vec, 0.5 * height))
    direction = v_sub(end, start)
    height = v_len(direction)
    if height <= 1.0e-9:
        return None
    axis_name = str(entry.get("axis", "Z")).upper()
    cls = str(entry.get("classification", "missing_bore_with_chamfer_candidate"))
    group = r20b_accepted_promotion_group(doc, parent_group)
    try:
        obj = doc.addObject("Part::Feature", "X1_R20B_AcceptedPromotedBore_%03d" % index)
        obj.Shape = Part.makeCylinder(radius, height, start, v_unit(direction))
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = (
            "X1 R20B accepted promoted bore %03d | %s | axis=%s | r=%.3f | depth=%.3f | evidence=%.2f"
            % (index, cls, axis_name, radius, height, float(entry.get("evidence_score", 0.0)))
        )
        try:
            obj.ViewObject.ShapeColor = color_for_axis(axis_name)
            obj.ViewObject.Transparency = int(X1_CYLINDER_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_common_feature_metadata(
            obj,
            family="accepted_bore",
            role="guarded_missing_bore_promotion",
            stage="R20B_guarded_missing_bore_promotion",
            kind="accepted_path_promotion",
            profile="MISSING_BORE_WITH_CHAMFER_PROMOTED",
        )
        add_custom_text_property(obj, "X1_Decision", "accepted_path_promoted")
        add_custom_text_property(obj, "X1_PromotionState", "accepted_path_promoted")
        add_custom_text_property(obj, "X1_PromotionReason", promote_reason)
        add_custom_text_property(obj, "X1_ReviewPolicy", X1_R20B_ACCEPTED_PROMOTION_LABEL)
        add_custom_text_property(obj, "X1_AcceptedFeature", "True")
        add_custom_text_property(obj, "X1_AcceptedPathPromotion", "True")
        add_custom_text_property(obj, "X1_Axis", axis_name)
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_RadiusMin", "%.6f" % float(entry.get("radius_min", radius)))
        add_custom_text_property(obj, "X1_RadiusMax", "%.6f" % float(entry.get("radius_max", radius)))
        add_custom_text_property(obj, "X1_Depth", "%.6f" % float(height))
        add_custom_text_property(obj, "X1_EvidenceScore", "%.6f" % float(entry.get("evidence_score", 0.0)))
        add_custom_text_property(obj, "X1_EvidenceCount", int(entry.get("evidence_count", 0)))
        add_custom_text_property(obj, "X1_SourceKinds", ",".join(entry.get("source_kinds", [])))
        add_custom_text_property(obj, "X1_SourceClasses", ",".join(entry.get("classes", [])))
        add_custom_text_property(obj, "X1_EvidenceSources", " | ".join(entry.get("evidence_sources", [])[:8]))
        add_custom_text_property(obj, "X1_PlacementCopied", str(copied))
        add_to_group(group, obj)
        x1_msg(
            "    X1 R20B accepted promoted bore %03d: class=%s axis=%s radius=%.4f radius_range=%.4f..%.4f depth=%.4f evidence=%.2f accepted=True promotion_state=accepted_path_promoted reason=%s"
            % (
                index,
                cls,
                axis_name,
                radius,
                float(entry.get("radius_min", radius)),
                float(entry.get("radius_max", radius)),
                height,
                float(entry.get("evidence_score", 0.0)),
                promote_reason,
            )
        )
        return obj
    except Exception as exc:
        x1_warn("  X1 R20B accepted promoted bore %03d skipped: %s" % (index, exc))
        return None

def r20b_emit_consolidated_entry_marker(doc, parent_group, entry, index, source_obj):
    if bool(entry.get("suppress_marker", False)):
        return None
    if not bool(X1_R20B_CONSOLIDATED_LEDGER_MARKERS):
        return None
    radius = float(entry.get("radius", 0.0))
    start = entry.get("start")
    end = entry.get("end")
    if radius <= X1_MIN_RADIUS or start is None or end is None:
        return None
    direction = v_sub(end, start)
    height = v_len(direction)
    if height <= 1.0e-9:
        axis_vec = axis_vector(entry.get("axis", "Z"))
        height = max(radius, float(entry.get("depth", radius)))
        start = v_sub(entry.get("center", v_new(0, 0, 0)), v_scale(axis_vec, 0.5 * height))
        direction = axis_vec
    cls = str(entry.get("classification", "tessellated_bore_candidate"))
    group = r20b_consolidated_group_for_class(doc, parent_group, cls)
    try:
        obj = doc.addObject("Part::Feature", "X1_R20B_Consolidated_%03d_%s" % (index, r20b_obj_name_safe(cls, 28)))
        obj.Shape = Part.makeCylinder(radius, height, start, v_unit(direction))
        copied = copy_source_placement_if_needed(obj, source_obj)
        obj.Label = "X1 R20B DIAGNOSTIC consolidated %03d | %s | axis=%s | r=%.3f | evidence=%.2f" % (
            index, cls, entry.get("axis", "?"), radius, float(entry.get("evidence_score", 0.0))
        )
        try:
            obj.ViewObject.ShapeColor = r20b_marker_color_for_class(cls)
            obj.ViewObject.Transparency = int(X1_R20B_CONSOLIDATED_MARKER_TRANSPARENCY)
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
        add_common_feature_metadata(obj, family="consolidated_tessellated_ledger", role=cls, stage="R20B_consolidated_tessellated_ledger", kind="diagnostic", profile=",".join(entry.get("profiles", [])[:4]))
        add_custom_text_property(obj, "X1_Axis", entry.get("axis", "?"))
        add_custom_text_property(obj, "X1_Radius", "%.6f" % radius)
        add_custom_text_property(obj, "X1_RadiusMin", "%.6f" % float(entry.get("radius_min", radius)))
        add_custom_text_property(obj, "X1_RadiusMax", "%.6f" % float(entry.get("radius_max", radius)))
        add_custom_text_property(obj, "X1_Depth", "%.6f" % float(height))
        add_custom_text_property(obj, "X1_EvidenceScore", "%.6f" % float(entry.get("evidence_score", 0.0)))
        add_custom_text_property(obj, "X1_EvidenceCount", int(entry.get("evidence_count", 0)))
        add_custom_text_property(obj, "X1_SourceKinds", ",".join(entry.get("source_kinds", [])))
        add_custom_text_property(obj, "X1_SourceClasses", ",".join(entry.get("classes", [])))
        add_custom_text_property(obj, "X1_EvidenceSources", " | ".join(entry.get("evidence_sources", [])[:6]))
        add_custom_text_property(obj, "X1_PlacementCopied", str(copied))
        add_to_group(group, obj)
        return obj
    except Exception as exc:
        x1_warn("  X1 R20B consolidated marker %03d skipped: %s" % (index, exc))
        return None


def emit_r20b_consolidated_tessellated_ledger(doc, parent_group, accepted_primitives, rejected_groups, fast_stacks, side_probe, source_obj, bb, accepted_promotion_group=None):
    totals = defaultdict(int)
    if not bool(X1_R20B_ENABLE_CONSOLIDATED_TESSELLATED_LEDGER):
        return totals
    if parent_group is None:
        return totals

    entries = []
    for idx, prim in enumerate(accepted_primitives or [], start=1):
        e = r20b_entry_from_accepted_primitive(prim, idx)
        if e is not None:
            entries.append(e)
    for stack in list(fast_stacks or []):
        e = r20b_entry_from_fast_stack(stack, accepted_primitives)
        if e is not None:
            entries.append(e)
    for pair in list((side_probe or {}).get("_pairs", [])):
        e = r20b_entry_from_side_pair(pair, accepted_primitives)
        if e is not None:
            entries.append(e)
    for cand in list((side_probe or {}).get("_singles", [])):
        e = r20b_entry_from_side_single(cand, accepted_primitives)
        if e is not None:
            entries.append(e)

    consolidated = r20b_consolidate_entries(entries)
    marker_index = 1
    review_marker_index = 1
    promotion_preview_index = 1
    accepted_promotion_index = 1
    for entry in consolidated:
        cls = str(entry.get("classification", ""))
        review_tier = r20b_review_tier_for_entry(entry)
        allowed_preview, preview_reason = r20b_is_promotion_preview_allowed(entry)
        allowed_accepted, accepted_reason = r20b_is_accepted_promotion_allowed(entry)
        entry["review_tier"] = review_tier or ""
        entry["promotion_preview"] = bool(allowed_preview and not allowed_accepted)
        entry["promotion_state"] = "accepted_path_promoted" if allowed_accepted else ("preview_only" if allowed_preview else "blocked")
        entry["promotion_reason"] = accepted_reason if allowed_accepted else preview_reason
        entry["accepted"] = bool(allowed_accepted)
        entry["accepted_path_promotion"] = bool(allowed_accepted)
        totals["entries"] += 1
        r20b_record_structured_ledger_entry(entry, source_obj, int(totals.get("entries", 0)))
        if cls in ("stable_covered", "stable_radius_may_be_chamfer_mouth"):
            totals["stable_covered"] += 1
        elif cls in ("missing_bore_with_chamfer_candidate", "missing_feature_candidate"):
            totals["missing"] += 1
        elif cls in ("chamfer_mouth_with_smaller_body_candidate", "tessellated_chamfer_body_candidate", "accepted_bore_may_be_chamfer_mouth_or_mixed_radius"):
            totals["chamfer_body"] += 1
        elif cls in ("weak_single_side_context", "suppressed_near_accepted", "tessellation_only_unanchored", "side_pair_context_only", "side_pair_context_high_depth_ratio"):
            totals["suppressed"] += 1
        else:
            totals["tessellated"] += 1
        if bool(entry.get("suppress_marker", False)):
            totals["suppressed"] += 1
        if marker_index <= int(X1_R20B_CONSOLIDATED_MAX_MARKERS):
            obj = r20b_emit_consolidated_entry_marker(doc, parent_group, entry, marker_index, source_obj)
            if obj is not None:
                totals["markers"] += 1
                marker_index += 1
        if review_marker_index <= int(X1_R20B_REVIEW_MARKER_MAX_MARKERS):
            review_obj = r20b_emit_tessellated_review_marker(doc, parent_group, entry, review_marker_index, source_obj)
            if review_obj is not None:
                totals["review_markers"] += 1
                if review_tier == "A":
                    totals["review_markers_tier_a"] += 1
                elif review_tier == "B":
                    totals["review_markers_tier_b"] += 1
                review_marker_index += 1
        if allowed_accepted and accepted_promotion_index <= int(X1_R20B_ACCEPTED_PROMOTION_MAX_MARKERS):
            accepted_obj = r20b_emit_accepted_promotion_cylinder(doc, accepted_promotion_group or parent_group, entry, accepted_promotion_index, source_obj)
            if accepted_obj is not None:
                totals["accepted_path_promotions"] += 1
                accepted_promotion_index += 1
        if (allowed_preview and not allowed_accepted) and promotion_preview_index <= int(X1_R20B_PROMOTION_PREVIEW_MAX_MARKERS):
            preview_obj = r20b_emit_promotion_preview_cylinder(doc, parent_group, entry, promotion_preview_index, source_obj)
            if preview_obj is not None:
                totals["promotion_preview"] += 1
                promotion_preview_index += 1
        suppression_reason = r20b_review_suppression_reason(entry) if (bool(entry.get("suppress_marker", False)) or "side_pair" in set(str(v) for v in entry.get("source_kinds", []))) else ""
        x1_msg(
            "  X1 R20B consolidated ledger %03d: class=%s axis=%s r=%.4f r_range=%.4f..%.4f depth=%.4f evidence=%.2f sources=%s suppressed=%s review_tier=%s promotion_preview=%s accepted_promotion=%s%s" % (
                int(totals.get("entries", 0)),
                cls,
                entry.get("axis", "?"),
                float(entry.get("radius", 0.0)),
                float(entry.get("radius_min", 0.0)),
                float(entry.get("radius_max", 0.0)),
                float(entry.get("depth", 0.0)),
                float(entry.get("evidence_score", 0.0)),
                "+".join(entry.get("source_kinds", [])),
                bool(entry.get("suppress_marker", False)),
                review_tier or "-",
                bool(entry.get("promotion_preview", False)),
                bool(entry.get("accepted_path_promotion", False)),
                (" reason=" + suppression_reason) if suppression_reason else "",
            )
        )
    x1_msg(
        "  R20B consolidated tessellated ledger: entries=%d markers=%d review_markers=%d tier_a=%d tier_b=%d promotion_preview=%d accepted_promotions=%d stable=%d chamfer/body=%d missing=%d tessellated=%d suppressed=%d" % (
            int(totals.get("entries", 0)),
            int(totals.get("markers", 0)),
            int(totals.get("review_markers", 0)),
            int(totals.get("review_markers_tier_a", 0)),
            int(totals.get("review_markers_tier_b", 0)),
            int(totals.get("promotion_preview", 0)),
            int(totals.get("accepted_path_promotions", 0)),
            int(totals.get("stable_covered", 0)),
            int(totals.get("chamfer_body", 0)),
            int(totals.get("missing", 0)),
            int(totals.get("tessellated", 0)),
            int(totals.get("suppressed", 0)),
        )
    )
    return totals


# =============================================================================
# R20B structured ledger export
# =============================================================================


def r20b_float_value(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def r20b_int_value(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def r20b_vec_components(value):
    try:
        return (float(value.x), float(value.y), float(value.z))
    except Exception:
        return (0.0, 0.0, 0.0)


def r20b_decision_for_entry(entry):
    cls = str(entry.get("classification", ""))
    if bool(entry.get("accepted_path_promotion", False)):
        return "accepted_path_promoted"
    if bool(entry.get("promotion_preview", False)):
        return "promotion_preview_only"
    if cls in ("stable_covered", "stable_radius_may_be_chamfer_mouth"):
        return "accepted_stable"
    if cls in ("side_pair_context_only", "side_pair_context_high_depth_ratio", "weak_single_side_context"):
        return "diagnostic_context"
    if bool(entry.get("suppress_marker", False)):
        return "suppressed_raw"
    if cls in (
        "missing_bore_with_chamfer_candidate",
        "missing_feature_candidate",
        "chamfer_mouth_with_smaller_body_candidate",
        "tessellated_chamfer_body_candidate",
        "accepted_bore_may_be_chamfer_mouth_or_mixed_radius",
    ):
        return "diagnostic_strong"
    return "diagnostic_context"


def r20b_risk_flags_for_entry(entry):
    flags = []
    cls = str(entry.get("classification", ""))
    source_kinds = set(str(s) for s in entry.get("source_kinds", []))
    radius = max(r20b_float_value(entry.get("radius", 0.0)), 1.0e-9)
    depth = r20b_float_value(entry.get("depth", 0.0))
    if cls == "tessellation_only_unanchored":
        flags.append("fast_only_tessellation_unanchored")
    if cls in ("side_pair_context_only", "side_pair_context_high_depth_ratio") or source_kinds.issubset({"side_pair"}):
        flags.append("side_pair_only_no_independent_confirmation")
    if depth / radius >= r20b_float_value(X1_R20B_SIDE_PAIR_CONTEXT_MAX_DEPTH_RADIUS_RATIO):
        flags.append("high_depth_radius_ratio")
    if bool(entry.get("suppress_marker", False)):
        flags.append("visual_marker_suppressed")
    if bool(entry.get("accepted_path_promotion", False)):
        flags.append("accepted_path_promoted")
    elif bool(entry.get("promotion_preview", False)):
        flags.append("promotion_preview_only_not_accepted")
    return sorted(set(flags))


def r20b_record_structured_ledger_entry(entry, source_obj, local_index):
    if not bool(X1_R20B_EXPORT_STRUCTURED_LEDGER):
        return
    try:
        object_label = getattr(source_obj, "Label", getattr(source_obj, "Name", "Object"))
    except Exception:
        object_label = "Object"
    cx, cy, cz = r20b_vec_components(entry.get("center", None))
    sx, sy, sz = r20b_vec_components(entry.get("start", None))
    ex, ey, ez = r20b_vec_components(entry.get("end", None))
    decision = r20b_decision_for_entry(entry)
    flags = r20b_risk_flags_for_entry(entry)
    row = {
        "schema_version": X1_R20B_LEDGER_SCHEMA_VERSION,
        "macro_version": X1_VERSION,
        "object_name": str(object_label),
        "feature_id": "%s:%03d" % (str(object_label), int(local_index)),
        "family": "feature_evidence_ledger",
        "classification": str(entry.get("classification", "")),
        "decision": decision,
        "axis": str(entry.get("axis", "?")),
        "center_x": cx,
        "center_y": cy,
        "center_z": cz,
        "start_x": sx,
        "start_y": sy,
        "start_z": sz,
        "end_x": ex,
        "end_y": ey,
        "end_z": ez,
        "radius": r20b_float_value(entry.get("radius", 0.0)),
        "radius_min": r20b_float_value(entry.get("radius_min", 0.0)),
        "radius_max": r20b_float_value(entry.get("radius_max", 0.0)),
        "depth": r20b_float_value(entry.get("depth", 0.0)),
        "evidence_score": r20b_float_value(entry.get("evidence_score", 0.0)),
        "evidence_count": r20b_int_value(entry.get("evidence_count", 0)),
        "merged_count": r20b_int_value(entry.get("merged_count", 1)),
        "source_system": "+".join(str(s) for s in entry.get("source_kinds", [])),
        "source_classes": "+".join(str(c) for c in entry.get("classes", [])),
        "profiles": "+".join(str(p) for p in entry.get("profiles", [])),
        "evidence_sources": " | ".join(compact_source_name(s, 180) for s in entry.get("evidence_sources", [])),
        "suppress_marker": bool(entry.get("suppress_marker", False)),
        "risk_flags": "+".join(flags),
        "review_tier": str(entry.get("review_tier", "") or r20b_review_tier_for_entry(entry) or ""),
        "suppression_reason": r20b_review_suppression_reason(entry),
        "promotion_preview": bool(entry.get("promotion_preview", False)),
        "promotion_state": str(entry.get("promotion_state", "blocked")),
        "promotion_reason": str(entry.get("promotion_reason", "")),
        "accepted_path_promotion": bool(entry.get("accepted_path_promotion", False)),
    }
    try:
        X1_R20B_STRUCTURED_LEDGER_ROWS.append(row)
    except Exception:
        pass


def r20b_doc_export_directory(doc):
    candidates = []
    try:
        filename = str(getattr(doc, "FileName", "") or "")
        if filename:
            candidates.append(os.path.dirname(filename))
    except Exception:
        pass
    try:
        candidates.append(os.path.expanduser("~/Desktop"))
    except Exception:
        pass
    try:
        candidates.append(os.getcwd())
    except Exception:
        pass
    candidates.append("/tmp")
    for path in candidates:
        try:
            if path and os.path.isdir(path) and os.access(path, os.W_OK):
                return path
        except Exception:
            continue
    return "/tmp"


def r20b_write_structured_ledger_exports(doc):
    rows = list(X1_R20B_STRUCTURED_LEDGER_ROWS)
    if not bool(X1_R20B_EXPORT_STRUCTURED_LEDGER):
        return []
    out_paths = []
    out_dir = r20b_doc_export_directory(doc)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = "%s_%s" % (X1_R20B_EXPORT_BASENAME, stamp)
    if rows:
        fieldnames = [
            "schema_version", "macro_version", "object_name", "feature_id", "family",
            "classification", "decision", "axis",
            "center_x", "center_y", "center_z", "start_x", "start_y", "start_z", "end_x", "end_y", "end_z",
            "radius", "radius_min", "radius_max", "depth",
            "evidence_score", "evidence_count", "merged_count",
            "source_system", "source_classes", "profiles", "evidence_sources", "suppress_marker", "risk_flags",
            "review_tier", "suppression_reason", "promotion_preview", "promotion_state", "promotion_reason", "accepted_path_promotion",
        ]
    else:
        fieldnames = ["schema_version", "macro_version", "object_name", "feature_id", "family", "classification", "decision", "axis"]
    try:
        if bool(X1_R20B_EXPORT_CSV_LEDGER):
            csv_path = os.path.join(out_dir, base + ".csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            out_paths.append(csv_path)
    except Exception as exc:
        x1_warn("R20B CSV ledger export failed: %s" % exc)
    try:
        if bool(X1_R20B_EXPORT_JSON_LEDGER):
            json_path = os.path.join(out_dir, base + ".json")
            payload = {
                "schema_version": X1_R20B_LEDGER_SCHEMA_VERSION,
                "macro_version": X1_VERSION,
                "generated_at": stamp,
                "row_count": len(rows),
                "rows": rows,
            }
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            out_paths.append(json_path)
    except Exception as exc:
        x1_warn("R20B JSON ledger export failed: %s" % exc)
    for path in out_paths:
        x1_msg("R20B structured ledger export: %s" % path)
    if not out_paths:
        x1_msg("R20B structured ledger export: no file written")
    return out_paths


if __name__ == "__main__":
    main()
else:
    # FreeCAD also executes macro files by loading them, where __name__ can be
    # different depending on the runner. Running here keeps .py and .FCMacro
    # behavior consistent.
    main()
