import numpy as np
import os


def downscale_all(img, mask, edges, downscale):
    """
    Downscales all the inputs by a given scale.
    :param img: A sparse  flow map - h x w x 2
    :param mask: A binary mask  - h x w x 1
    :param edges:An edges map  - h x w x 1
    :param downscale: Downscaling factor.
    :return: the downscaled versions of the inputs
    """
    from skimage.util.shape import view_as_blocks
    from skimage.transform import rescale
    img[:, :, 0][mask == -1] = np.nan
    img[:, :, 1][mask == -1] = np.nan

    img = img[:(img.shape[0] - (img.shape[0] % downscale)), :(img.shape[1] - (img.shape[1] % downscale)), :]

    blocks = view_as_blocks(img, (downscale, downscale, 2))
    img = np.nanmean(blocks, axis=(-2, -3, -4))

    mask = np.ones_like(img)
    mask[np.isnan(img)] = -1
    mask = mask[:, :, 0]
    img[np.isnan(img)] = 0

    if edges is not None:
        edges = edges[:(edges.shape[0] - (edges.shape[0] % downscale)), :(edges.shape[1] - (edges.shape[1] % downscale))]
        edges = rescale(edges, 1 / float(downscale), preserve_range=True)

    return img, mask, edges


def inverse_of_map(of_map, of_mask, scale):
    """
    Inverse the input flow map turns (x1,y1) -> (dx, dy) to (x2,y2) -> (-dx, -dy),
    :param of_map: h x w x 2 optical flow map
    :param of_mask: h x w binary mask for the existing pixels in the flow map
    :param scale: The scale used to downsample the flow map before feeding it into the function
    :return: A flow map with the inverse input optical flow map.
    """
    map_count = np.zeros((of_map.shape[0], of_map.shape[1]))
    rev_of_map = np.zeros_like(of_map, dtype=np.float32)
    for y in range(of_map.shape[0]):
        for x in range(of_map.shape[1]):
            if of_mask[y, x] == 1:
                rev_x = (x * scale + of_map[y, x, 0]) / scale
                rev_y = (y * scale + of_map[y, x, 1]) / scale
                rev_x = int(np.floor(rev_x + 0.5))
                rev_y = int(np.floor(rev_y + 0.5))
                if 0 < rev_x < rev_of_map.shape[1] and 0 < rev_y < rev_of_map.shape[0]:
                    map_count[rev_y, rev_x] += 1
                    rev_of_map[rev_y, rev_x] += (-rev_of_map[rev_y, rev_x] - of_map[y, x]) / map_count[rev_y, rev_x]
    return rev_of_map, (np.asarray(map_count > 0, dtype=np.float32) * 2) - 1


def mean_map_of_and_rev_ba(of_map, of_mask, rev_of_map_ba, rev_of_mask_ba):
    """
    Calculates the mean flow map between the optical flow map from A to B and the inverse flow map from B to A
    :param of_map: flow map from A to B
    :param of_mask: binary mask of AB flow map
    :param rev_of_map_ba: inverse flow map from B to A
    :param rev_of_mask_ba: binary mask of BA inverse flow map
    :return: the mean flow map
    """
    of_map_nan = of_map.copy()
    of_map_nan[np.stack((of_mask, of_mask), axis=2) == -1] = np.nan
    rev_of_map_ba_nan = rev_of_map_ba.copy()
    rev_of_map_ba_nan[np.stack((rev_of_mask_ba, rev_of_mask_ba), axis=2) == -1] = np.nan

    mean_map = np.nanmean(np.stack((of_map_nan, rev_of_map_ba_nan), axis=3), axis=3, dtype=np.float32)
    mean_map_mask = -(np.asarray(np.isnan(mean_map), np.float32) * 2 - 1)[:, :, 0]
    mean_map[np.isnan(mean_map)] = 0

    return mean_map, mean_map_mask


def create_mean_map_ab_ba(img, mask, img_ba, mask_ba, scale):
    """
    A wrapper for the functions: inverse_of_map and mean_map_of_and_rev_ba
    :param img: flow map from A to B
    :param mask: binary mask of AB flow map
    :param img_ba: flow map from B to A
    :param mask_ba: binary mask of BA flow map
    :param scale: The scale used to downsample the flow map before feeding it into the function
    :return: the mean flow map
    """
    rev_of_map_ba, rev_of_mask_ba = inverse_of_map(img_ba, mask_ba, scale=scale)
    mean_map, mean_map_mask = mean_map_of_and_rev_ba(img, mask, rev_of_map_ba, rev_of_mask_ba)

    return mean_map, mean_map_mask


def calc_variational_inference_map(imgA_filename, imgB_filename, flo_filename, out_filename, dataset):
    """
    Run the post processing variation energy minimization.
    :param imgA_filename: filename of RGB image A of the image pair.
    :param imgB_filename: filename of RGB image B of the image pair.
    :param flo_filename: filename of flow map to set as initialization.
    :param out_filename: filename for the output flow map.
    :param dataset: sintel / kitti
    """
    shell_command = './SrcVariational/variational_main ' + imgA_filename + ' ' + imgB_filename + ' ' + flo_filename + ' ' + out_filename + ' -' + dataset
    exit_code = os.system(shell_command)
