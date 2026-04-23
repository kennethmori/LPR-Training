# Detector Augmentation Recommendation

This project's detector dataset is still relatively small, with `329` training images in the current split. For that reason, on-the-fly augmentation is useful, but it should stay mild and realistic because the target object is a license plate with text that can be distorted too easily.

## Next Training Direction

The next detector training run should use `yolo26n` as the starting checkpoint instead of the larger variant used previously. This is a good fit for the current project because the deployment target is CPU-oriented, and `yolo26n` is better aligned with fast inference on modest hardware while still benefiting from careful training choices.

To maximize the useful features of `yolo26n`, the training plan should follow these best practices:

- keep image size at `640` unless profiling shows the hardware can comfortably handle a larger size
- use realistic on-the-fly augmentation rather than aggressive synthetic distortion
- keep labels clean and preserve the current train/val/test split
- train with enough epochs for convergence, but rely on patience-based early stopping to avoid wasting time
- compare results using both validation metrics and real sample images from the target camera
- prefer a stable detector that performs well on the actual camera feed over a model that looks better only on synthetic augmentation

Recommended starting checkpoint for the next run:

```bash
python scripts/train_detector.py --data configs/detector_data.yaml --model yolo26n.pt
```

## Recommended Approach

Use custom on-the-fly augmentation during detector training instead of relying only on the generic default profile. The goal is to simulate real camera variation such as lighting, small viewpoint changes, and slight scale shifts without making plates unreadable or unrealistic.

Suggested training profile:

```python
model.train(
    data=str(Path(args.data)),
    epochs=args.epochs,
    imgsz=args.imgsz,
    batch=args.batch,
    project=args.project,
    name=args.name,
    patience=args.patience,

    # Plate-friendly augmentation
    hsv_h=0.01,
    hsv_s=0.4,
    hsv_v=0.25,
    degrees=3.0,
    translate=0.08,
    scale=0.2,
    shear=1.0,
    perspective=0.0005,
    fliplr=0.0,
    flipud=0.0,
    mosaic=0.3,
    mixup=0.0,
    copy_paste=0.0,
    erasing=0.1,
    close_mosaic=10,
)
```

## Why These Settings

- `hsv_h=0.01`, `hsv_s=0.4`, `hsv_v=0.25`: adds moderate color and lighting variation for outdoor camera conditions.
- `degrees=3.0`: allows small rotation without creating unrealistic plate angles.
- `translate=0.08`, `scale=0.2`: helps the detector tolerate slight framing and distance changes.
- `shear=1.0`, `perspective=0.0005`: adds only a very light geometric change to mimic mild camera viewpoint shifts.
- `fliplr=0.0`, `flipud=0.0`: avoids mirrored or upside-down plates, which are not realistic.
- `mosaic=0.3`: keeps some mosaic benefit for detection robustness but avoids the stronger distortion from a full default mosaic level.
- `mixup=0.0`, `copy_paste=0.0`: disabled because these often make text-heavy license plate targets less realistic.
- `erasing=0.1`: allows a small amount of occlusion simulation without overly damaging the plate region.
- `close_mosaic=10`: disables mosaic in the final training epochs so the detector can finish on more natural-looking samples.

## Practical Notes

- On-the-fly augmentation does not create new stored files. The training set remains `329` images, but each epoch can present different variants of those images.
- With `80` epochs, the model sees about `329 x 80 = 26,320` training exposures.
- This does not mean there are `26,320` unique labeled images. It means the model repeatedly sees varied transformed versions of the original training set.

## What To Avoid

Avoid aggressive settings that may make plates unrealistic or characters hard to learn:

- very high `mosaic`
- strong `mixup`
- strong `shear`
- strong `perspective`
- horizontal or vertical flips
- very heavy blur or distortion

## Recommended Validation Workflow

Train at least two detector runs and compare them:

1. baseline settings from the previous run
2. this plate-friendly augmentation profile

Compare:

- validation `mAP50`
- validation `mAP50-95`
- behavior on real sample images from your target camera

If the augmented run improves validation metrics and looks more stable on real samples, keep it. If not, reduce augmentation further rather than increasing it.

## Summary Recommendation

For the next detector experiment, use `yolo26n.pt` together with the plate-friendly augmentation profile in this document. The goal is not to push the strongest possible augmentation, but to get the best real-world result from `yolo26n` by preserving realistic plate appearance, keeping training stable, and optimizing for CPU-friendly deployment.
