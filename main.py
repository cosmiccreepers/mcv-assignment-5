import os
import pandas as pd
import numpy as np
import matplotlib
import cv2
import gc
import models as m
import visuals as v
from keras.layers import Input, Dense, Activation, Dropout, Conv2D, MaxPooling2D, Flatten, AveragePooling2D, BatchNormalization
from keras.layers.advanced_activations import ReLU
from keras.models import Sequential
from keras.optimizers import SGD, rmsprop, Adam
from sklearn.model_selection import train_test_split
from keras import backend as K
import tensorflow as tf
from tensorflow.python.client import device_lib

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

config = tf.ConfigProto(
    gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.8)
    # device_count = {'GPU': 1}
)
config.gpu_options.allow_growth = True
session = tf.Session(config=config)

# session = tf.Session(config=config)
# session.run()

np.random.seed(1337)  # for reproducibility

batch_size = 32
nb_classes = 40
nb_epoch = 30

class_dict = {}


def paths_list_from_directory(directory):
    """Creates a list of paths within a given directory"""
    # loop over files and make a list of full paths then add to the path list
    path_list = [os.path.join(directory, f) for f in os.listdir(os.path.join(directory))]

    return path_list


def load_image(filename, num_classes):
    """Loads an image from a given path"""
    # use the global class_dict variable
    global class_dict
    # [1] Get the file category and make the conversion. Last 7 chars of name are extension, a number and and underscore
    dir, file = os.path.split(filename)
    file_class = file[:-8]

    # If the class is already in the dict then use the classification associated, else create a new one and add to dict
    if file_class in class_dict.keys():
        label = np.eye(num_classes)[class_dict.get(file_class)]
    else:
        label = np.eye(num_classes)[len(class_dict)]
        class_dict[file_class] = len(class_dict)

    # [2] Load the image in greyscale with opencv.
    # use cv2 image read function, and greyscale parameter
    image = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)

    # [3] Find the dimension that is the smallest between the height and the width and assign it to the crop_dim var
    # get values of height and width from image shape
    height, width = image.shape[:2]

    # create a tuple that flags 1 on the larger dimesion, height in position 0 and width in position 1
    if height < width:
        crop_dim = (0, 1)
    else:
        crop_dim = (1, 0)

    # [4] Crop the centre of the image based on the crop_dim dimension for both the height and width.
    # use our crop_dim tuple in calculation to determine what the margin (distance from edge of image)
    margin = int(crop_dim[0] * (height-width)/2 + crop_dim[1] * (width-height)/2)
    # use the crop_dim and calculated margin to exclude the margin from the appropriate dimension
    image = image[(crop_dim[1]*margin):(width - crop_dim[1]*margin), (crop_dim[0]*margin):(height-crop_dim[0]*margin)]

    # [5] Resize the image to 48 x 48 and divide it with 255.0 to normalise it to floating point format.
    # use opencv resize function
    image = cv2.resize(image, (200, 200))

    # set the image as a float type and divide by 255.0 to normalize
    image.astype(float)
    image = image/255.0

    return image, label


def DataGenerator(img_addrs, batch_size, num_classes):
    """A data generator for use in image processing for NN"""
    # We removed the img_labels from DataGenerator as the load_image returns a label from the path anyway
    while 1:
        # Ensure randomisation per epoch using np.random.shuffle
        # addrs_labels = list(zip(img_addrs, img_labels))
        np.random.shuffle(img_addrs)
        # img_addrs, img_labels = zip(*addrs_labels)

        X = []
        Y = []

        # we removed count var from here, loop over range of images
        for j in range(len(img_addrs)):

            # [1] Call the load_images function and append the image in X.
            image, label = load_image(img_addrs[j], num_classes)
            X.append(image)
            # [2] Create a one-hot encoding with np.eye and append the one-hot vector to Y.
            Y.append(label)  # already receiving 1-hot from load_image

        # [3] Compare the count and batch_size (hint: modulo operation) and if so:
        # we use j+1 as count var was previously equivalent to this
        # when we hit a value of j+1 that is a multiple of batch size we run below block
            if ((j+1) % batch_size) == 0:
                #   - Use yield to return X,Y as numpy arrays with types 'float32' and 'uint8' respectively
                X = np.array(X, dtype=np.float32)
                X = X.reshape(batch_size, 200, 200, 1)
                Y = np.array(Y, dtype=np.uint8)
                yield X, Y

                #   - delete X,Y
                del X
                del Y

                #   - set X,Y to []
                X = []
                Y = []

                # garbage collect
                gc.collect()


if __name__ == "__main__":

    # pull paths from function and shuffle these before splitting to train and val
    paths = paths_list_from_directory('JPEGImages')
    np.random.shuffle(paths)

    # Use train test split to split to default 0.75 train and 0.25 test
    # best was startin with 3x3 finishing with 3x3 and 1x1 max pools (11.0% on test)
    train, val = train_test_split(paths)
    with tf.Session(config=config) as sess:
        model = Sequential()
        model.add(Conv2D(128, kernel_size=(5, 5), strides=(1, 1), activation='relu', input_shape=(200, 200, 1)))
        # model.add(Conv2D(128, kernel_size=(3, 3), strides=(1, 1), activation='relu', input_shape=(200, 200, 1)))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(3, 3)))
        model.add(Conv2D(256, kernel_size=(3, 3), strides=(1, 1), activation='relu'))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(3, 3)))
        model.add(Conv2D(256, kernel_size=(1, 1), strides=(1, 1), activation='relu'))
        model.add(BatchNormalization())
        model.add(Conv2D(256, kernel_size=(3, 3), strides=(1, 1), activation='relu'))
        model.add(BatchNormalization())
        model.add(Conv2D(512, kernel_size=(3, 3), strides=(1, 1), activation='relu'))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Conv2D(512, kernel_size=(3, 3), strides=(1, 1), activation='relu'))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(2, 2)))
        # model.add(Conv2D(512, kernel_size=(3, 3), strides=(2, 2), activation='relu'))
        # model.add(Conv2D(512, kernel_size=(3, 3), strides=(2, 2), activation='relu'))
        # model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Flatten())
        model.add(Dense(4608, activation='relu')) # make it the size of what comes out of the flatten
        model.add(BatchNormalization())
        model.add(Dropout(0.2))
        model.add(Dense(2048, activation='relu'))
        model.add(BatchNormalization())
        model.add(Dropout(0.2))
        model.add(Dense(2048, activation='relu'))
        model.add(BatchNormalization())
        model.add(Dropout(0.2))
        model.add(Dense(nb_classes, activation='softmax'))

        # gradient decent parameters
        sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
        # rms = rmsprop(lr=0.01, rho=0.9, epsilon=None, decay=0.0)
        # ad = Adam(lr=0.01, beta_1=0.9, beta_2=0.999, epsilon=None, decay=0.0, amsgrad=False)

        # model.compile(optimizer=sgd,
        #              loss='categorical_crossentropy',
        #              metrics=['accuracy'])

        model.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])

        # print a summary of the model
        model.summary()

        # fit the model with our created generator, validate on the generator with the validation data over 10 batches
        history = model.fit_generator(DataGenerator(train, batch_size, nb_classes), epochs=nb_epoch,
                                      steps_per_epoch=64, verbose=1,
                                      validation_data=DataGenerator(val, batch_size, nb_classes),
                                      validation_steps=10)

        # score by doing a full run over the validation set
        score = model.evaluate_generator(DataGenerator(val, batch_size, nb_classes), verbose=0, steps=15)
        m.save_model(model, "model0")
        m.pickle_it(history, "model0_output")

    v.plot_epoch_accuracy(history.history['acc'], history.history['val_acc'], "plot_model0.png")
    v.write_history_csv(history,"history.csv")

    print('Test score:', score[0])
    print('Test accuracy:', score[1])
    print(class_dict)
