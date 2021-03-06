# Copyright (c) 2018-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

"""Perform inference on a single video or all videos with a certain extension
(e.g., .mp4) in a folder.
"""

from detectron.infer_simple import *
import subprocess as sp
import numpy as np
import json
import cv2

class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32,
                              np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

def get_resolution(filename):
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
               '-show_entries', 'stream=width,height', '-of', 'csv=p=0', filename]
    pipe = sp.Popen(command, stdout=sp.PIPE, bufsize=-1)
    while True:
        for line in pipe.stdout:
            w, h = line.decode().strip().split(',')
            return int(w), int(h)

def read_video(filename):
    ow, oh = get_resolution(filename)
    #ow = int(ow)
    #oh = int(oh)
    #w, h = 432, 368
    #dim = (w, h)
    command = ['ffmpeg',
            '-i', filename,
            '-f', 'image2pipe',
            '-pix_fmt', 'bgr24',
            '-vsync', '0',
            '-vcodec', 'rawvideo', '-']

    pipe = sp.Popen(command, stdout=sp.PIPE, bufsize=-1)
    #time.sleep(10)
    while True:
        data = pipe.stdout.read(ow*oh*3)
        if not data:
            break
        #yield cv2.resize(np.frombuffer(data, dtype=np.uint8), dim)
        yield np.frombuffer(data, dtype='uint8').reshape(oh, ow, 3)


def main(args):
    logger = logging.getLogger(__name__)
    merge_cfg_from_file(args.cfg)
    cfg.NUM_GPUS = 1
    args.weights = cache_url(args.weights, cfg.DOWNLOAD_CACHE)
    assert_and_infer_cfg(cache_urls=False, make_immutable=False)
    model = infer_engine.initialize_model_from_cfg(args.weights)
    #dummy_coco_dataset = dummy_datasets.get_coco_dataset()



    if os.path.isdir(args.im_or_folder):
        im_list = glob.iglob(args.im_or_folder + '/*.' + args.image_ext)
    else:
        im_list = [args.im_or_folder]

    for video_name in im_list:
        out_name = os.path.join(
                args.output_dir, os.path.basename(video_name)
            )
        print('Processing {}'.format(video_name))

        boxes = []
        segments = []
        keypoints = []

        for frame_i, im in enumerate(read_video(video_name)):
            #w, h = 432, 368
            #dim = (w, h)
            #print(im)
            #img = cv2.resize(im , dim, interpolation = cv2.INTER_AREA)
            print(im.shape)
            
            logger.info('Frame {}'.format(frame_i))
            timers = defaultdict(Timer)
            t = time.time()
            try:
                with c2_utils.NamedCudaScope(0):
                    #print(np.uint8(im))
                    cls_boxes, cls_segms, cls_keyps = infer_engine.im_detect_all(
                        model, im, None, timers=timers
                    )
                logger.info('Inference time: {:.3f}s'.format(time.time() - t))
                for k, v in timers.items():
                    logger.info(' | {}: {:.3f}s'.format(k, v.average_time))

                #print(cls_boxes)
                #print(cls_segms)
                #print(cls_keyps)


                boxes.append(cls_boxes)
                segments.append(cls_segms)
                keypoints.append(cls_keyps)

            except BaseException as err:
                print(f"Warning: c2_utils.NamedCudaScope failed for frame {frame_i}")
                print(f"Unexpected {err=}, {type(err)=}")
        
        # Video resolution
        metadata = {
            'w': im.shape[1],
            'h': im.shape[0],
        }

        clbox = json.dumps(boxes, cls=NumpyEncoder)
        clseg = json.dumps(segments, cls=NumpyEncoder)
        clkey = json.dumps(keypoints, cls=NumpyEncoder)
        clmta = json.dumps(metadata, cls=NumpyEncoder)

        #TODO: Debug then remove this.
        with open(out_name.replace(".mp4", "cls_boxes.json"), "w") as f:
            f.write(clbox + '\n')

        with open(out_name.replace(".mp4", "cls_segms.json"), "w") as f:
            f.write(clseg + '\n')
        
        with open(out_name.replace(".mp4", "cls_keyps.json"), "w") as f:
            f.write(clkey + '\n')

        with open(out_name.replace(".mp4", "cls_metad.json"), "w") as f:
            f.write(clmta + '\n')

        np.savez_compressed(out_name, boxes=boxes, segments=segments, keypoints=keypoints, metadata=metadata)

        clboxfile = open(out_name.replace(".mp4", "cls_boxes.json"), "r")        
        clbox = json.load(clboxfile)

        clsegfile = open(out_name.replace(".mp4", "cls_segms.json"), "r")
        clseg = json.load(clsegfile)
        
        clkeyfile = open(out_name.replace(".mp4", "cls_keyps.json"), "r")
        clkey = json.load(clkeyfile)

        clmtafile = open(out_name.replace(".mp4", "cls_metad.json"), "r")
        clmta = json.load(clmtafile)

        np.savez_compressed('alt'+out_name, boxes=clbox, segments=clseg, keypoints=clkey, metadata=clmta)


if __name__ == '__main__':
    workspace.GlobalInit(['caffe2', '--caffe2_log_level=0'])
    setup_logging(__name__)
    args = parse_args()
    main(args)
