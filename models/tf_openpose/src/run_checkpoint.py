import argparse
import logging

import tensorflow as tf
tf.compat.v1.disable_eager_execution()

from networks import get_network

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

config = tf.compat.v1.ConfigProto()
config.gpu_options.allocator_type = 'BFC'
config.gpu_options.per_process_gpu_memory_fraction = 0.95
config.gpu_options.allow_growth = True


if __name__ == '__main__':
    """
    Use this script to just save graph and checkpoint.
    While training, checkpoints are saved. You can test them with this python code.
    """
    parser = argparse.ArgumentParser(description='Tensorflow Pose Estimation Graph Extractor')
    parser.add_argument('--model', type=str, default='mobilenet_thin', help='cmu / mobilenet / mobilenet_thin')
    args = parser.parse_args()

    input_node = tf.compat.v1.placeholder(tf.float32, shape=(None, None, None, 3), name='image')

    with tf.compat.v1.Session(config=config) as sess:
        net, _, last_layer = get_network(args.model, input_node, sess, trainable=False)

        tf.io.write_graph(sess.graph_def, './tmp', 'graph.pb', as_text=True)

        graph = tf.compat.v1.get_default_graph()
        dir(graph)
        for n in tf.compat.v1.get_default_graph().as_graph_def().node:
            if 'concat_stage' not in n.name:
                continue
            print(n.name)

        saver = tf.compat.v1.train.Saver(max_to_keep=100)
        saver.save(sess, '/Users/ildoonet/repos/tf-openpose/tmp/chk', global_step=1)
