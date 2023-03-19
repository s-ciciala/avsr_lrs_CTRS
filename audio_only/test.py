import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
from torch.utils.data.datapipes.utils import decoder

from config import args
from models.audio_net import AudioNet
from models.lrs2_char_lm import LRS2CharLM
from data.lrs3_dataset import LRS3Main
from data.utils import collate_fn
from utils.general import evaluate

def print_predictions(model, testLoader, loss_function, device, testParams):
    model.eval()
    with torch.no_grad():
        for data in testLoader:
            inputs, targets, inputPercentages, targetSizes = data
            inputs, targets = inputs.to(device), targets.to(device)
            out, outputSizes = model(inputs, inputPercentages)
            decodedPreds = decoder.decode(out, outputSizes, testParams)
            for j in range(len(decodedPreds)):
                print("Model prediction:", decodedPreds[j][0])

#
def evaluate(model, dataLoader, loss_function, device, testParams):
    model.eval()
    totalLoss, totalCER, totalWER, totalChars, totalWords = 0, 0, 0, 0, 0
    with torch.no_grad():
        for data in dataLoader:
            inputs, targets, inputPercentages, targetSizes = data
            inputs, targets = inputs.to(device), targets.to(device)
            out, outputSizes = model(inputs, inputPercentages)
            loss = loss_function(out.transpose(0, 1), targets, outputSizes, targetSizes)
            totalLoss += loss.item()
            decodedPreds = decoder.decode(out, outputSizes, testParams)
            for j in range(len(decodedPreds)):
                print("Model prediction:", decodedPreds[j][0])

def main():

    np.random.seed(args["SEED"])
    torch.manual_seed(args["SEED"])
    gpuAvailable = torch.cuda.is_available()
    device = torch.device("cuda" if gpuAvailable else "cpu")
    kwargs = {"num_workers":args["NUM_WORKERS"], "pin_memory":True} if gpuAvailable else {}
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


    #declaring the test dataset and test dataloader
    audioParams = {"stftWindow":args["STFT_WINDOW"], "stftWinLen":args["STFT_WIN_LENGTH"], "stftOverlap":args["STFT_OVERLAP"]}
    if args["TEST_DEMO_NOISY"]:
        noiseParams = {"noiseFile":args["DATA_DIRECTORY"] + "/noise.wav", "noiseProb":1, "noiseSNR":args["NOISE_SNR_DB"]}
    else:
        noiseParams = {"noiseFile":args["DATA_DIRECTORY"] + "/noise.wav", "noiseProb":0, "noiseSNR":args["NOISE_SNR_DB"]}
    testData = LRS3Main("test", args["DATA_DIRECTORY"], args["MAIN_REQ_INPUT_LENGTH"], args["CHAR_TO_INDEX"], args["STEP_SIZE"],
                        audioParams, noiseParams)
    testLoader = DataLoader(testData, batch_size=args["BATCH_SIZE"], collate_fn=collate_fn, shuffle=True, **kwargs)


    if args["TRAINED_MODEL_FILE"] is not None:

        print("\nTrained Model File: %s" %(args["TRAINED_MODEL_FILE"]))

        #declaring the model, loss function and loading the trained model weights
        model = AudioNet(args["TX_NUM_FEATURES"], args["TX_ATTENTION_HEADS"], args["TX_NUM_LAYERS"],
                         args["PE_MAX_LENGTH"],
                         args["AUDIO_FEATURE_SIZE"], args["TX_FEEDFORWARD_DIM"], args["TX_DROPOUT"],
                         args["NUM_CLASSES"])

        # model.load_state_dict(torch.load(args["CODE_DIRECTORY"] + args["TRAINED_MODEL_FILE"], map_location=device))
        saved_state_dict = torch.load(args["CODE_DIRECTORY"] + args["TRAINED_MODEL_FILE"], map_location=device)
        new_state_dict = {}
        for k, v in saved_state_dict.items():
            name = k.replace('module.', '')  # remove the "module." prefix
            new_state_dict[name] = v
        model.load_state_dict(new_state_dict)
        model.to(device)
        loss_function = nn.CTCLoss(blank=0, zero_infinity=True)


        # #declaring the language model
        # lm = LRS2CharLM()
        # lm.load_state_dict(torch.load(args["TRAINED_LM_FILE"], map_location=device))
        # lm.to(device)
        if not args["USE_LM"]:
            lm = None


        print("\nTesting the trained model .... \n")

        beamSearchParams = {"beamWidth":args["BEAM_WIDTH"], "alpha":args["LM_WEIGHT_ALPHA"], "beta":args["LENGTH_PENALTY_BETA"],
                            "threshProb":args["THRESH_PROBABILITY"]}
        testParams = {"decodeScheme":args["TEST_DEMO_DECODING"], "beamSearchParams":beamSearchParams, "spaceIx":args["CHAR_TO_INDEX"][" "],
                      "eosIx":args["CHAR_TO_INDEX"]["<EOS>"], "lm":lm}

        #evaluating the model over the test set
        evaluate(model, testLoader, loss_function, device, testParams)

        # #evaluating the model over the test set
        # testLoss, testCER, testWER = evaluate(model, testLoader, loss_function, device, testParams)
        #
        # #printing the test set loss, CER and WER
        # print("Test Loss: %.6f || Test CER: %.3f || Test WER: %.3f" %(testLoss, testCER, testWER))
        # print("\nTesting Done.\n")


    else:
        print("Path to the trained model file not specified.\n")

    return


if __name__ == "__main__":
    main()