import numpy as np
import pytest
from deeplabcut.pose_estimation_tensorflow.lib import trackingutils


@pytest.fixture()
def ellipse():
    params = {"x": 0, "y": 0, "width": 2, "height": 4, "theta": np.pi / 2}
    return trackingutils.Ellipse(**params)


def test_ellipse(ellipse):
    assert ellipse.aspect_ratio == 2
    assert ellipse.geometry is not None
    np.testing.assert_equal(
        ellipse.contains_points(np.asarray([[0, 0], [10, 10]])), [True, False]
    )


def test_ellipse_similarity(ellipse):
    assert ellipse.calc_iou_with(ellipse) == 1
    assert ellipse.calc_similarity_with(ellipse) == 1


def test_ellipse_fitter():
    fitter = trackingutils.EllipseFitter()
    assert fitter.fit(np.random.rand(2, 2)) is None
    xy = np.asarray([[-2, 0], [2, 0], [0, 1], [0, -1]], dtype=np.float)
    assert fitter.fit(xy) is not None
    fitter.sd = 0
    el = fitter.fit(xy)
    assert np.isclose(el.parameters, [0, 0, 4, 2, 0]).all()


def test_ellipse_tracker(ellipse):
    tracker1 = trackingutils.EllipseTracker(ellipse.parameters)
    assert tracker1.id == 0
    tracker2 = trackingutils.EllipseTracker(ellipse.parameters)
    assert tracker2.id == 1
    tracker1.update(ellipse.parameters)
    assert tracker1.hit_streak == 1
    state = tracker1.predict()
    np.testing.assert_equal(ellipse.parameters, state)
    _ = tracker1.predict()
    assert tracker1.hit_streak == 0


def test_sort_ellipse():
    tracklets = dict()
    mot = trackingutils.SORTEllipse(1, 1, 0.6)
    poses = np.random.rand(2, 10, 3)
    trackers = mot.track(poses[..., :2])
    assert trackers.shape == (2, 7)
    trackingutils.fill_tracklets(tracklets, trackers, poses, imname=0)
    assert all(id_ in tracklets for id_ in trackers[:, -2])


def test_tracking(real_assemblies, real_tracklets):
    tracklets_ref = real_tracklets.copy()
    _ = tracklets_ref.pop("header", None)
    tracklets = dict()
    mot_tracker = trackingutils.SORTEllipse(1, 1, 0.6)
    for ind, assemblies in real_assemblies.items():
        animals = np.stack([ass.data[:, :3] for ass in assemblies])
        trackers = mot_tracker.track(animals[..., :2])
        trackingutils.fill_tracklets(tracklets, trackers, animals, ind)
    assert len(tracklets) == len(tracklets_ref)


def test_calc_bboxes_from_keypoints():
    xy = np.asarray([[[0, 0, 1]]])
    np.testing.assert_equal(
        trackingutils.calc_bboxes_from_keypoints(xy, 10), [[-10, -10, 10, 10, 1]]
    )
    np.testing.assert_equal(
        trackingutils.calc_bboxes_from_keypoints(xy, 20, 10), [[-10, -20, 30, 20, 1]]
    )

    width = 200
    height = width * 2
    xyp = np.zeros((1, 2, 3))
    xyp[:, 1, :2] = width, height
    xyp[:, 1, 2] = 1
    with pytest.raises(ValueError):
        _ = trackingutils.calc_bboxes_from_keypoints(xyp[..., :2])

    bboxes = trackingutils.calc_bboxes_from_keypoints(xyp)
    np.testing.assert_equal(bboxes, [[0, 0, width, height, 0.5]])

    slack = 20
    bboxes = trackingutils.calc_bboxes_from_keypoints(xyp, slack=slack)
    np.testing.assert_equal(bboxes, [[-slack, -slack, width + slack, height + slack, 0.5]])

    offset = 50
    bboxes = trackingutils.calc_bboxes_from_keypoints(xyp, offset=offset)
    np.testing.assert_equal(bboxes, [[offset, 0, width + offset, height, 0.5]])
