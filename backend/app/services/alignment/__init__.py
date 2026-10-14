from dataclasses import dataclass
import cv2
import numpy as np
from PIL import Image


@dataclass
class AlignmentResult:
    image: Image.Image
    metadata: dict


def preprocess(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"))
    return cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(gray)


def align_submission_to_template(template_image: Image.Image, submission_image: Image.Image) -> AlignmentResult:
    """Conservative ORB registration. Failed geometry is never auto-gradable."""
    template_size = template_image.size
    def reduced(image):
        ratio = min(1.0, 1600 / max(image.size))
        size = (round(image.width * ratio), round(image.height * ratio))
        return preprocess(image.resize(size)), ratio
    template, tr = reduced(template_image)
    submission, sr = reduced(submission_image)
    detector = cv2.ORB_create(nfeatures=5000)
    tk, td = detector.detectAndCompute(template, None)
    sk, sd = detector.detectAndCompute(submission, None)
    meta = {"method": "orb_homography", "verified": False, "confidence": 0.0, "matches": 0, "inlier_ratio": 0.0}
    fallback = submission_image.resize(template_size)
    if td is None or sd is None or len(tk) < 12 or len(sk) < 12:
        return AlignmentResult(fallback, {**meta, "reason": "insufficient_features"})
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(sd, td, k=2)
    good = [m for pair in pairs if len(pair) == 2 for m, n in [pair] if m.distance < .72 * n.distance]
    meta["matches"] = len(good)
    if len(good) < 12:
        return AlignmentResult(fallback, {**meta, "reason": "insufficient_matches"})
    src = np.float32([sk[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([tk[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3)
    if homography is None or mask is None or not np.isfinite(homography).all():
        return AlignmentResult(fallback, {**meta, "reason": "homography_failed"})
    inliers = mask.ravel().astype(bool)
    ratio = float(inliers.mean())
    points = src[inliers].reshape(-1, 2)
    hull_area = cv2.contourArea(cv2.convexHull(points)) if len(points) >= 3 else 0
    spread = hull_area / (submission.shape[0] * submission.shape[1])
    full = np.diag([1 / tr, 1 / tr, 1]) @ homography @ np.diag([sr, sr, 1])
    corners = np.float32([[0, 0], [submission_image.width, 0], [submission_image.width, submission_image.height], [0, submission_image.height]]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(corners, full).reshape(-1, 2)
    area_ratio = abs(cv2.contourArea(transformed)) / (template_size[0] * template_size[1])
    convex = bool(cv2.isContourConvex(transformed))
    verified = ratio >= .55 and int(inliers.sum()) >= 12 and spread >= .12 and .65 <= area_ratio <= 1.5 and convex
    meta.update(inlier_ratio=ratio, inliers=int(inliers.sum()), feature_spread=float(spread), area_ratio=area_ratio,
                verified=verified, confidence=min(ratio, .99) if verified else 0.0,
                reason="registered" if verified else "unverified_geometry")
    if not verified:
        return AlignmentResult(fallback, meta)
    warped = cv2.warpPerspective(np.asarray(submission_image), full, template_size, borderValue=(255, 255, 255))
    return AlignmentResult(Image.fromarray(warped), meta)
