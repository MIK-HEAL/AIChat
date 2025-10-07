import live2d

import os
import traceback
import importlib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "hiyori_free_zh", "hiyori_free_zh", "runtime", "hiyori_free_t08.model3.json")

try:
    import live2d
    print("live2d module:", getattr(live2d, '__file__', str(live2d)))
    # show top-level attrs
    print("live2d attrs:", [a for a in dir(live2d) if not a.startswith('_')])

    # try to import v3 LAppModel
    from live2d.v3 import LAppModel as Live2DModel
    print("Imported LAppModel from live2d.v3")

    print(f"Model JSON path: {MODEL_PATH}")
    print("Exists?", os.path.exists(MODEL_PATH))

    model = Live2DModel()
    # only load JSON to validate API usage; loading may still raise if resources missing
    model.LoadModelJson(MODEL_PATH)
    print("LoadModelJson completed")

    # try setting expression if available
    try:
        model.SetExpression("normal")
        print("SetExpression called")
    except Exception as e:
        print("SetExpression failed:", e)

    # try starting a motion (may fail safely)
    try:
        model.StartRandomMotion("Idle")
        print("StartRandomMotion called")
    except Exception as e:
        print("StartRandomMotion failed:", e)

    # avoid calling Draw() here because it may require an active OpenGL context
    print("Done — model initialized (Draw not called to avoid OpenGL context requirements)")

except Exception:
    print("Exception while using live2d:")
    traceback.print_exc()
