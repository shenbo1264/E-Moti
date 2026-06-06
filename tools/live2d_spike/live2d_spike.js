(function () {
  const statusNode = document.getElementById("status");
  const params = new URLSearchParams(window.location.search);
  const modelUrl = params.get("model") || "";
  const expressionId = params.get("expression") || "";
  const motionGroup = params.get("motionGroup") || "";
  const visualActions = parseJsonParam(params.get("actions"), []);
  const mappedActions = parseJsonParam(params.get("mappedActions"), []);
  const expressionMap = parseMapParam(
    params.get("expressionMap"),
    {
      calm: "F01",
      joy: "F02",
      excited: "F02",
      surprised: "F03",
      sadness: "F04",
      sleepy: "F05",
      focused: "F06",
    },
  );
  const motionMap = parseMapParam(
    params.get("motionMap"),
    {
      Default: "Idle",
      Play: "TapBody",
      Raised: "TapBody",
      TouchHead: "TapBody",
    },
  );

  const state = {
    loaded: false,
    error: "",
    modelUrl,
    expressionId,
    motionGroup,
    visualActions,
    mappedActions,
    appliedVisualActions: [],
    expressionApplied: false,
    motionApplied: false,
    frameSamples: 0,
    modelSize: null,
  };

  window.live2dSpike = state;

  function setStatus(message) {
    statusNode.textContent = message;
  }

  function fail(error) {
    state.error = String(error && error.stack ? error.stack : error);
    setStatus(`error\n${state.error}`);
  }

  function parseJsonParam(value, fallback) {
    if (!value) {
      return fallback;
    }
    try {
      return JSON.parse(value);
    } catch (error) {
      fail(`invalid JSON query parameter: ${error}`);
      return fallback;
    }
  }

  function parseMapParam(value, fallback) {
    if (!value) {
      return fallback;
    }
    const parsed = parseJsonParam(value, fallback);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      return fallback;
    }
    const result = {};
    for (const [key, mapped] of Object.entries(parsed)) {
      if (typeof key === "string" && key && typeof mapped === "string" && mapped) {
        result[key] = mapped;
      }
    }
    return result;
  }

  function fitModel(app, model) {
    const bounds = model.getLocalBounds();
    const stageWidth = app.renderer.width;
    const stageHeight = app.renderer.height;
    const scale = Math.min(stageWidth / bounds.width, stageHeight / bounds.height) * 0.82;
    model.anchor.set(0.5, 0.5);
    model.scale.set(scale);
    model.position.set(stageWidth / 2, stageHeight * 0.54);
    state.modelSize = {
      width: Math.round(bounds.width),
      height: Math.round(bounds.height),
      scale,
    };
  }

  async function applyPresentation(model) {
    if (expressionId && typeof model.expression === "function") {
      await model.expression(expressionId);
      state.expressionApplied = true;
    }
    if (motionGroup && typeof model.motion === "function") {
      await model.motion(motionGroup);
      state.motionApplied = true;
    }
    await applyVisualActions(model, visualActions);
    await applyMappedActions(model, mappedActions);
  }

  async function applyVisualActions(model, actions) {
    if (!Array.isArray(actions)) {
      return;
    }
    for (const action of actions) {
      if (!action || typeof action !== "object") {
        continue;
      }
      const actionType = action.type;
      const actionId = action.id;
      if (typeof actionType !== "string" || typeof actionId !== "string") {
        continue;
      }
      if (actionType === "expression" && typeof model.expression === "function") {
        const mappedExpression = expressionMap[actionId];
        if (mappedExpression) {
          await model.expression(mappedExpression);
          state.expressionApplied = true;
          state.appliedVisualActions.push({
            type: "expression",
            id: actionId,
            mapped: mappedExpression,
          });
        }
      }
      if (actionType === "motion" && typeof model.motion === "function") {
        const mappedMotion = motionMap[actionId];
        if (mappedMotion) {
          await model.motion(mappedMotion);
          state.motionApplied = true;
          state.appliedVisualActions.push({
            type: "motion",
            id: actionId,
            mapped: mappedMotion,
          });
        }
      }
    }
  }

  async function applyMappedActions(model, actions) {
    if (!Array.isArray(actions)) {
      return;
    }
    for (const action of actions) {
      if (!action || typeof action !== "object") {
        continue;
      }
      const actionType = action.type;
      const actionId = action.id;
      const mapped = action.mapped;
      if (typeof actionType !== "string" || typeof actionId !== "string" || typeof mapped !== "string") {
        continue;
      }
      if (actionType === "expression" && typeof model.expression === "function") {
        await model.expression(mapped);
        state.expressionApplied = true;
        state.appliedVisualActions.push({ type: "expression", id: actionId, mapped });
      }
      if (actionType === "motion" && typeof model.motion === "function") {
        await model.motion(mapped);
        state.motionApplied = true;
        state.appliedVisualActions.push({ type: "motion", id: actionId, mapped });
      }
    }
  }

  async function main() {
    if (!modelUrl) {
      fail("missing model query parameter");
      return;
    }
    if (!window.PIXI || !window.PIXI.live2d || !window.PIXI.live2d.Live2DModel) {
      fail("pixi-live2d-display cubism4 bundle is not loaded");
      return;
    }

    const canvas = document.getElementById("stage");
    const app = new PIXI.Application({
      view: canvas,
      autoStart: true,
      resizeTo: window,
      backgroundAlpha: 0,
      antialias: true,
    });

    const model = await PIXI.live2d.Live2DModel.from(modelUrl);
    window.live2dModel = model;
    app.stage.addChild(model);
    fitModel(app, model);
    await applyPresentation(model);

    app.ticker.add(() => {
      state.frameSamples += 1;
      if (state.frameSamples % 30 === 0) {
        setStatus(
          [
            "loaded",
            `model=${modelUrl}`,
            `expression=${expressionId || "(none)"} applied=${state.expressionApplied}`,
            `motionGroup=${motionGroup || "(none)"} applied=${state.motionApplied}`,
            `visualActions=${state.appliedVisualActions.length}`,
            `frames=${state.frameSamples}`,
          ].join("\n"),
        );
      }
    });

    state.loaded = true;
    setStatus("loaded");
  }

  main().catch(fail);
})();
