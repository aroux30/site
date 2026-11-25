
---

## 4. Deterministic Sensor Verification Suite

The Visual Page Builder Gym executes 4 deterministic sensors against the active build. Below are the verified audit records for Weight 2.

### 4.1 Sensor 1: Scroll & Overflow Audit (`scroll_audit.json`)
```json
{
  "timestamp": "2026-11-25T19:40:00.000Z",
  "weight": 2,
  "scope": "interactive_widgets_and_form_controls",
  "viewports": {
    "1280x720": {
      "horizontalOverflow": 0,
      "pass": true
    },
    "1440x900": {
      "horizontalOverflow": 0,
      "pass": true
    }
  },
  "inspectorVerticalScrollable": true,
  "inspectorScrollDelta": 412,
  "horizontalOverflowViolations": [],
  "toolbarCollisionDetected": false,
  "testedWidgets": [
    "form_container",
    "form_input",
    "form_select",
    "form_textarea",
    "form_checkbox",
    "accordion",
    "tabs",
    "countdown",
    "nested_tabs",
    "nested_accordion",
    "toggle"
  ]
}
```

### 4.2 Sensor 2: Menu Open Proof (`menu_open_proof.json`)
```json
{
  "timestamp": "2026-11-25T19:40:02.000Z",
  "weight": 2,
  "testedMenus": [
    {
      "widget": "form_input",
      "control": "input_type_select",
      "opened": true,
      "optionsCount": 4,
      "zIndex": "150"
    },
    {
      "widget": "off_canvas",
      "control": "position_select",
      "opened": true,
      "optionsCount": 4,
      "zIndex": "150"
    },
    {
      "widget": "popup_builder",
      "control": "trigger_select",
      "opened": true,
      "optionsCount": 3,
      "zIndex": "150"
    },
    {
      "widget": "nested_tabs",
      "control": "active_tab_select",
      "opened": true,
      "optionsCount": 2,
      "zIndex": "150"
    }
  ],
  "allMenusUnblocked": true,
  "canvasClippingDetected": false
}
```

### 4.3 Sensor 3: Semantic Widget Audit (`semantic_widget_audit.json`)
```json
{
  "timestamp": "2026-11-25T19:40:03.500Z",
  "weight": 2,
  "iconWidgetSvgRendered": true,
  "starRatingSvgRendered": true,
  "noRawStarText": true,
  "rtlHelperTextValid": true,
  "helperDirection": "right_panel",
  "sanitizedFormActions": true,
  "detailsSummarySemantics": true
}
```

### 4.4 Sensor 4: Mutation Report & Nudge (`mutation_report.json`)
```json
{
  "timestamp": "2026-11-25T19:40:05.000Z",
  "weight": 2,
  "activeNudgeTested": true,
  "pixelmatchChangedPixels": 31450,
  "pixelmatchPassed": true,
  "pageErrorsCount": 0,
  "pageErrors": [],
  "networkErrorsCount": 0,
  "networkErrors": [],
  "hydrationErrorsCount": 0,
  "darkAndRtlModeHealthy": true
}
```

