# Predictors fail to load pre-trained checkpoints on PyTorch >= 2.6 (UnpicklingError: weights_only)

**Describe the bug**
With PyTorch >= 2.6, every predictor in `lighthouse.models` fails to load the published pre-trained checkpoints with an `UnpicklingError`.

PyTorch 2.6 changed the default of `torch.load` to `weights_only=True`. The checkpoints store their config in `ckpt['opt']` as an `easydict.EasyDict`, which the weights-only unpickler rejects. `BasePredictor.__init__` calls `torch.load(ckpt_path, map_location='cpu')` without `weights_only`, so it hits this for every model (Moment-DETR, QD-DETR, EaTR, CG-DETR, TR-DETR, UVCOM, TaskWeave).

`training/train.py` and `training/evaluate.py` already pass `weights_only=False` (added in d0be10b), but `lighthouse/models.py` does not. CI pins `torch==2.1.0`, so it does not catch this.

**To reproduce**
Environment: lighthouse `main` (3e841d3), torch 2.15.0+cpu, Python 3.11, CPU.
```python
from lighthouse.models import QDDETRPredictor
model = QDDETRPredictor('results/qd_detr/qvhighlight/clip/best.ckpt', device='cpu', feature_name='clip')
```
The checkpoint is from the pre-trained weights `results.zip` linked in the README. The Zenodo test weights (for example `clip_cg_detr_qvhighlight.ckpt`) fail the same way.

**Traceback**
```
  File "lighthouse/models.py", line 337, in __init__
    super().__init__('qd_detr', ckpt_path, device,
  File "lighthouse/models.py", line 67, in __init__
    ckpt = torch.load(ckpt_path, map_location='cpu')
  File ".../torch/serialization.py", line 1615, in load
    raise pickle.UnpicklingError(_get_wo_message(str(e))) from None
_pickle.UnpicklingError: Weights only load failed. ...
	(1) In PyTorch 2.6, we changed the default value of the `weights_only` argument in `torch.load` from `False` to `True`. ...
	WeightsUnpickler error: Unsupported global: GLOBAL easydict.EasyDict was not an allowed global by default. ...
```

**Proposed fix**
Pass `weights_only=False` in `BasePredictor.__init__`, matching `training/train.py` and `training/evaluate.py`. The keyword exists since torch 1.13, so it also works with the torch 2.1 used in CI. `torch.serialization.add_safe_globals` would keep weights-only loading, but it only exists from torch 2.4. I'm happy to open a PR.

