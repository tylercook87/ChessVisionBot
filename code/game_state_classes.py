import chess
import chess.engine
import numpy as np
from board_basics import *
import chessboard_detection
import pyautogui
import cv2
import mss
import math
from random import randint
from time import sleep
import copy
import os
import time
import sys 


from chess.engine import EngineTerminatedError


class NoValidPosition(Exception):

   pass
class PositionChanged(Exception):

   pass


class Board_position:
    def __init__(self,minX,minY,maxX,maxY,factor):
        self.minX = minX
        self.minY = minY
        self.maxX = maxX
        self.maxY = maxY
        self.factor =factor
        self.current = None

    def print_custom(self):
        return ("from " + str(self.minX) + "," + str(self.minY) + " to " + str(self.maxX) + ","+ str(self.maxY))

class Game_state:

    def __init__(self):
        self.we_play_white = True #This store the player color, it will be changed later
        self.moves_to_detect_before_use_engine = -1 #The program uses the engine to play move every time that this variable is 0
        self.expected_move_to_detect = "" #This variable stores the move we should see next, if we don't see the right one in the next iteration, we wait and try again. This solves the slow transition problem: for instance, starting with e2e4, the screenshot can happen when the pawn is on e3, that is a possible position. We always have to double check that the move is done.
        self.previous_chessboard_image = [] #Storing the chessboard image from previous iteration
        self.executed_moves = [] #Store the move detected on san format
        self.engine = chess.engine.SimpleEngine.popen_uci("engine/stockfish-13-64")
        # self.engine = chess.engine.SimpleEngine.popen_uci("engine/komodo-11.01-64-osx")
        self.board = chess.Board() #This object comes from the "chess" package, the moves are stored inside it (and it has other cool features such as showing all the "legal moves")
        self.board_position_on_screen = []
        self.sct = mss.mss()


    def check_for_castling(self,potential_starts, potential_arrivals):
        valid_move_string = ""
        # Detect castling king side with white
        if ("e1" in potential_starts) and ("h1" in potential_starts) and ("f1" in potential_arrivals) and (
                "g1" in potential_arrivals):
            valid_move_string = "e1g1"
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "e1"))
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "f1"))

        # Detect castling queen side with white
        if ("e1" in potential_starts) and ("a1" in potential_starts) and ("c1" in potential_arrivals) and (
                "d1" in potential_arrivals):
            valid_move_string = "e1c1"
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "e1"))
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "c1"))

        # Detect castling king side with black
        if ("e8" in potential_starts) and ("h8" in potential_starts) and ("f8" in potential_arrivals) and (
                "g8" in potential_arrivals):
            valid_move_string = "e8g8"
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "e8"))
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "f8"))

        # Detect castling queen side with black
        if ("e8" in potential_starts) and ("a8" in potential_starts) and ("c8" in potential_arrivals) and (
                "d8" in potential_arrivals):
            valid_move_string = "e8c8"
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "e8" ))
            potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == "c8"))
        
        return valid_move_string,potential_starts

    def get_valid_move(self, potential_starts, potential_arrivals, current_chessboard_image):

        print("Starts and arrivals:",potential_starts, potential_arrivals)
        if len( potential_arrivals)==0 and len(potential_starts)==0:
            return "",[]

        valid_move_string,potential_starts = self.check_for_castling(potential_starts, potential_arrivals)
        
        if valid_move_string:
            return valid_move_string,[potential_starts,potential_arrivals]


        rest = []
        if len(potential_starts)==2 and len(potential_arrivals)==0:
            print('recapture with same piece')

            capture_moves_own=list(self.board.generate_legal_captures())
            # print(capture_moves_own)
            for move in capture_moves_own:
                if chess.Move.uci(move)[:2] == potential_starts[0] or chess.Move.uci(move)[:2] == potential_starts[1]:
                    try:
                        self.board.push(move)
                    except:
                        continue

                    capture_moves_opponent = list(self.board.generate_legal_captures())
                    for move_opp in capture_moves_opponent:
                        if chess.Move.uci(move_opp)[:2] == potential_starts[0] or chess.Move.uci(move_opp)[:2] == potential_starts[1]:
                            self.board.pop()
                            potential_arrivals.append(chess.Move.uci(move)[-2:])
                            break



        for start in potential_starts:
            for arrival in potential_arrivals:

                # print("moves"+start+arrival)
                uci_move = start+arrival
                if start == arrival:
                    continue
                move = chess.Move.from_uci(uci_move)
                if move in self.board.legal_moves:
                    valid_move_string = uci_move
                    print(valid_move_string)
                    rest = []
                    if len(potential_starts) >= 2 or len(potential_arrivals) >= 2:
                        potential_starts = np.delete(potential_starts,np.argwhere(potential_starts == start))
                        rest = [potential_starts,potential_arrivals]
                else:
                    uci_move_promoted = uci_move + 'q'
                    promoted_move = chess.Move.from_uci(uci_move_promoted)
                    if promoted_move in self.board.legal_moves:
                        rest = []
                        valid_move_string = uci_move_promoted
                        print("There has been a promotion to queen")
                        if len(potential_starts) >= 2 or len(potential_arrivals) >= 2:
                            potential_starts = np.delete(potential_starts, np.argwhere(potential_starts == start))
                            rest = [potential_starts, potential_arrivals]
                    
        return valid_move_string, rest


    def register_move_if_needed(self):

        new_board = chessboard_detection.get_chessboard(self)
        old_board = self.previous_chessboard_image
        diff = cv2.absdiff(new_board, old_board)
        if diff.mean() == 0:
            return False, ([], []), (old_board, new_board)
        cv2.waitKey(50)
        new_board2 = chessboard_detection.get_chessboard(self)
        # cv2.waitKey(10)
        # new_board3 = chessboard_detection.get_chessboard(self)
        while cv2.absdiff(new_board,new_board2).mean()>0:# or cv2.absdiff(new_board,new_board3).mean()>0:
            new_board = chessboard_detection.get_chessboard(self)
            cv2.waitKey(50)
            new_board2 = chessboard_detection.get_chessboard(self)
            # cv2.waitKey(10)
            # new_board3 = chessboard_detection.get_chessboard(self)



        potential_starts, potential_arrivals = get_potential_moves(self.previous_chessboard_image,new_board,self.we_play_white)
        if len(potential_starts)>6 or len(potential_arrivals)>6:
            self.previous_chessboard_image=new_board
            raise PositionChanged
            # pass
        valid_move_string1, rest = self.get_valid_move(potential_starts,potential_arrivals,new_board)
        if rest:
            # print('premove to process')
            print("Valid move string 1:" + valid_move_string1)
            if len(valid_move_string1) > 0:
                valid_move_UCI = chess.Move.from_uci(valid_move_string1)
                valid_move_registered = self.register_move(valid_move_UCI,new_board)
                new_board = chessboard_detection.get_chessboard(self)
                potential_starts = rest[0]
                potential_arrivals = rest[1]
                valid_move_string1, rest = self.get_valid_move(potential_starts, potential_arrivals, new_board)
                if len(valid_move_string1) > 0:
                    valid_move_UCI = chess.Move.from_uci(valid_move_string1)
                    valid_move_registered = self.register_move(valid_move_UCI, new_board)

                    return True, valid_move_string1,(old_board,new_board)
        else:
            print("Valid move string 1:" + valid_move_string1)
            if len(valid_move_string1) > 0:
                valid_move_UCI = chess.Move.from_uci(valid_move_string1)
                valid_move_registered = self.register_move(valid_move_UCI,new_board)
                return True, valid_move_string1,(old_board,new_board)
        # if len(potential_arrivals)>0 or len(potential_starts)>0:

        return False, (potential_starts,potential_arrivals),(old_board,new_board)
    


        

    def register_move(self,move,board_image):
        if move in self.board.legal_moves:
            print("Move has been registered")
            self.executed_moves = np.append(self.executed_moves,self.board.san(move))
            self.board.push(move)
            self.moves_to_detect_before_use_engine  -= 1
            self.previous_chessboard_image = board_image
            return True
        else:
            return False

    def get_square_center(self,square_name):
        row,column = convert_square_name_to_row_column(square_name,self.we_play_white)
        position = self.board_position_on_screen
        centerX = int(position.minX + (column + 0.5) *(position.maxX-position.minX)/8)
        centerY = int(position.minY + (row + 0.5) *(position.maxY-position.minY)/8)
        return centerX,centerY

    def play_next_move(self,factor,strength,variance):
        pyautogui.PAUSE = 0
        starttime = time.time()
        print("\nUs to play: Calculating next move")



        try:
            info = self.engine.analyse(self.board, chess.engine.Limit(time=0.01))  # chess.engine.Limit(depth=20))

            score = info["score"]
            if strength<=2000:
                move_time = (strength + (randint(1, variance))) / 1000
                engine_process = self.engine.play(self.board,  chess.engine.Limit(time=move_time))
                
                # self.board.push(engine_process.move)
                # score_move = self.engine.analyse(self.board, chess.engine.Limit(time=0.01))["score"]
            
                
                # if (score_move.relative.score() == None and score.relative.score() != None):
                #     self.board.pop()

                # elif (score_move.relative.score() != None and score.relative.score() == None):
                #     self.board.pop()
                #     fen_str,detected_board = self.build_fen(self.we_are_white,rochade = '-' )
                #     self.board.set_fen(fen_str)
                #     return self.play_next_move(factor,strength,variance)

                # elif (score_move.relative.score() == None and score.relative.score() == None):
                #     if (abs(score_move.relative.score(mate_score=100000)) > abs(score.relative.score(mate_score=100000))):
                #         self.board.pop()
                #     else:
                #         self.board.pop()
                #         fen_str,detected_board = self.build_fen(self.we_play_white,rochade="-")
                #         self.board.set_fen(fen_str)
                #         return self.play_next_move(factor,strength,variance)
                 
                # elif (abs(score_move.relative.score(mate_score=100000)) > abs(score.relative.score(mate_score=100000))):
                #     #bad move
                    
                #     self.board.pop()
                #     fen_str,detected_board = self.build_fen(self.we_play_white,rochade="-")
                #     self.board.set_fen(fen_str)
                #     return self.play_next_move(factor,strength,variance)

                #     #rescan board and find new move
                # else:
                #     self.board.pop()

            else:
                print('depth_mode')
                move_time = time.time() 
                engine_process = self.engine.play(self.board, chess.engine.Limit(depth=20))
                move_time = time.time() - move_time

                self.board.push(engine_process.move)
                score_move = self.engine.analyse(self.board, chess.engine.Limit(time=0.01))["score"]
            
                
                if (score_move.relative.score() == None and score.relative.score() != None):
                    self.board.pop()

                elif (score_move.relative.score() != None and score.relative.score() == None):
                    self.board.pop()
                    fen_str,detected_board = self.build_fen(self.we_play_white,rochade="-")
                    self.board.set_fen(fen_str)
                    return self.play_next_move(factor,strength,variance)

                elif (score_move.relative.score() == None and score.relative.score() == None):
                    if (abs(score_move.relative.score(mate_score=100000)) > abs(score.relative.score(mate_score=100000))):
                        self.board.pop()
                    else:
                        self.board.pop()
                        fen_str,detected_board = self.build_fen(self.we_play_white,rochade="-")
                        self.board.set_fen(fen_str)
                        return self.play_next_move(factor,strength,variance)
                 
                elif (abs(score_move.relative.score(mate_score=100000)) > abs(score.relative.score(mate_score=100000))):
                    #bad move
                    
                    self.board.pop()
                    fen_str,detected_board = self.build_fen(self.we_play_white,rochade="-")
                    self.board.set_fen(fen_str)
                    return self.play_next_move(factor,strength,variance)

                    #rescan board and find new move
                else:
                    self.board.pop()
            

        except EngineTerminatedError:
            print('restart')
            self.engine = chess.engine.SimpleEngine.popen_uci("engine/stockfish-13-64")
            # self.engine = chess.engine.SimpleEngine.popen_uci("engine/komodo-11.01-64-osx")

            return 0,0

        postthink = time.time()

        best_move = engine_process.move
        best_move_string = best_move.uci()
        #print("Play next move")

        #print(bestMove)
        origin_square = best_move_string[0:2]
        destination_square = best_move_string[2:4]
        

        centerXOrigin, centerYOrigin = self.get_square_center(origin_square)
        centerXDest, centerYDest = self.get_square_center(destination_square)
        factor /= 2
        centerXOrigin *= factor
        centerYOrigin *= factor
        centerXDest *= factor
        centerYDest *= factor
        # print(f"preparetime: {time.time()-postthink}")

        # mousetime=time.time()
        # Having the positions we can drag the piece:
        pyautogui.moveTo(int(centerXOrigin), int(centerYOrigin), 0.0001)
        # pyautogui.click(clicks=2,button='left')
        pyautogui.dragTo(int(centerXOrigin), int(centerYOrigin) + 1, button='left', duration=0.2)  # This small click is used to get the focus back on the browser window

        pyautogui.dragTo(int(centerXDest), int(centerYDest), button='left', duration=0.11)
        # print(f"mousetime: {time.time()-mousetime}")

        if best_move.promotion != None:
            print("Promoting to a queen")
            # Deal with queen promotion:
            cv2.waitKey(100)
            pyautogui.dragTo(int(centerXDest), int(centerYDest) + 1, button='left',
                             duration=0.1)  # Always promoting to a queen

        print("Done playing move", origin_square, destination_square)
        # curr_chessboard = chessboard_detection.get_chessboard(self)
        # diff = cv2.absdiff(self.previous_chessboard_image,curr_chessboard)


        # if diff.mean() == 0:
        #     print('move_error')
        #     castling = self.get_castling_rights()
        #     fen,vis = self.build_fen(self.we_play_white, castling)
        #     self.board.set_fen(fen)
        #     self.moves_to_detect_before_use_engine = 0
        # else:
        #     self.moves_to_detect_before_use_engine = 2
        self.moves_to_detect_before_use_engine = 2
        # print(f"movetime: {time.time()-starttime-move_time}")
        return score, move_time


    def get_castling_rights(self):
        rights=''
        if self.board.has_kingside_castling_rights(True):
            rights+='K'
        if self.board.has_queenside_castling_rights(True):
            rights += 'Q'
        if self.board.has_kingside_castling_rights(False):
            rights+='k'
        if self.board.has_queenside_castling_rights(False):
            rights += 'q'
        if len(rights)==0:
            rights+='-'
        return rights

    def build_fen(self,we_are_white,rochade = 'KQkq' ):
        position_detection = chessboard_detection.get_chessboard(self, (1024, 1024))
        self.previous_chessboard_image = chessboard_detection.get_chessboard(self)
        # cv2.imshow('dsd',position_detection)
        # cv2.waitKey(0)
        #   board_basics.is_white_on_bottom(position_detection)
        self.we_play_white = we_are_white

        to_move = 'w' if we_are_white else 'b'

        self.moves_to_detect_before_use_engine = 0  # if v.get() else 1

        pieces = sorted(os.listdir('pieces'))

        vis_glob = np.array([])
        piece_notation = ['b', 'k', 'n', 'p', 'q', 'r', '*', 'B', 'K', 'N', 'P', 'Q', 'R']
        fen_str = ''

        # rochade = 'KQkq'


        order = range(8) if we_are_white else reversed(range(8))
        for i in order:
            vis = np.array([])

            image_list = [get_square_image(i, j, position_detection) for j in (range(8) if we_are_white else reversed(range(8)))]
            answers = piece_on_square_list(image_list)
            for answer in answers:
                im = cv2.imread(os.path.join('pieces', pieces[answer]))
                if vis.size == 0:
                    vis = im
                    fen_str += piece_notation[answer]
                else:
                    if we_are_white:
                        vis = np.concatenate((vis,im), axis=1)
                    else:
                        vis = np.concatenate((im, vis), axis=1)
                    fen_str += piece_notation[answer]

            fen_str += '/'
            if vis_glob.size == 0:
                vis_glob = vis
            else:
                if we_are_white:
                    vis_glob = np.concatenate(( vis_glob,vis), axis=0)
                else:
                    vis_glob = np.concatenate((vis, vis_glob), axis=0)

        fen_str = self.transform_fen(fen_str,to_move,rochade)
        # fen_str= fen_str.replace("  "," ")
        return fen_str,vis_glob

    def visulize_fen(self,fen):
        pass

    def transform_fen(self, fen_str, to_move, rochade, en_passant='-',halfmoves='0',move='1'):
        fen_str = fen_str[:-1] + ' ' + to_move + ' ' + rochade + ' ' + en_passant + ' ' + halfmoves + ' ' + move

        for i in range(len(fen_str)):
            if fen_str[i] == ' ':
                break
            count = 0
            if fen_str[i] == '*':
                while fen_str[i] == '*':
                    count += 1

                    fen_str = fen_str[0: i:] + fen_str[i + 1::]
                fen_str = fen_str[:i] + str(count) + fen_str[i:]
        return fen_str

    def our_side(self):
        # TODO use pawns to get side
        position_detection = chessboard_detection.get_chessboard(self, (800, 800))
        piece_notation = ['b', 'k', 'n', 'p', 'q', 'r', '*', 'B', 'K', 'N', 'P', 'Q', 'R']

        black_king_position=()
        white_king_position = ()
        order = range(8)
        for i in order:
            vis = np.array([])
            # order2 = range(8)
            image_list = [get_square_image(i, j, position_detection) for j in range(8)]
            answers = piece_on_square_list(image_list)
            if piece_notation.index('k') in answers:
                black_king_position = (i, 0)
            if piece_notation.index('K') in answers:
                white_king_position= (i,0)


        if not white_king_position or not black_king_position:
            raise NoValidPosition
        if black_king_position[0]<white_king_position[0]:
            return 'white'
        elif black_king_position[0]>white_king_position[0]:
            return 'black'
        else:
            return 'unsure'

   

    def build_fen_guess_side(self):

        position_detection = chessboard_detection.get_chessboard(self, (1024, 1024))
        position_detection2 = chessboard_detection.get_chessboard(self, (612, 612))

        self.previous_chessboard_image = chessboard_detection.get_chessboard(self)

        self.moves_to_detect_before_use_engine = 0  # if v.get() else 1

        fen_str = ''
        # position_detection = chessboard_detection.get_chessboard(self, (1024, 1024))
        piece_notation = ['b', 'k', 'n', 'p', 'q', 'r', '*', 'B', 'K', 'N', 'P', 'Q', 'R']

        pieces = sorted(os.listdir('pieces'))

        vis_glob = np.array([])

        rochade = '-'

        im_list = []
        black_king_position = -1
        white_king_position = -1

        prediction_time = 0

        for i in range(8):
            for j in range(8):

                # step_time = time.time()
                answer = piece_on_square(get_square_image(i, j, position_detection))
                answer2 = piece_on_square(get_square_image(i, j, position_detection2))
                if answer != answer2:
                    position_detection3 = chessboard_detection.get_chessboard(self, (2048, 2048))
                    answer = piece_on_square(get_square_image(i, j, position_detection3))


                # prediction_time += (time.time() - step_time)
                if piece_notation.index('k') == answer:
                    black_king_position = i*8+j
                if piece_notation.index('K') == answer:
                    white_king_position = i*8+j

                im = cv2.imread(os.path.join('pieces', pieces[answer]))
                im_list.append(im)
                fen_str += piece_notation[answer]

            fen_str += '/'



        print(f"-->Prediction: {prediction_time}")

        if  white_king_position ==-1 or  black_king_position==-1:
            raise NoValidPosition
        if black_king_position < white_king_position:

            for im_row in list(chunks(im_list, 8)):
                vis = np.array([])
                for img in im_row:
                    if vis.size == 0:
                        vis = img
                    else:
                        vis = np.concatenate((vis, img), axis=1)
                if vis_glob.size == 0:
                    vis_glob = vis
                else:
                    vis_glob = np.concatenate((vis_glob, vis), axis=0)
            self.we_play_white = True
            return True, self.transform_fen(fen_str, 'w', rochade), vis_glob

        else:

            for im_row in list(chunks((im_list), 8)):
                vis = np.array([])
                for img in im_row:
                    if vis.size == 0:
                        vis = img
                    else:
                        vis = np.concatenate((vis, img), axis=1)
                if vis_glob.size == 0:
                    vis_glob = vis
                else:
                    vis_glob = np.concatenate((vis_glob, vis), axis=0)
            self.we_play_white = False
            return False, self.transform_fen(((fen_str[:-1])[::-1] + '/'), 'b', rochade), vis_glob


# Create a function called "chunks" with two arguments, l and n:
def chunks(l, n):
    # For item i in a range that is a length of l,
    for i in range(0, len(l), n):
        # Create an index range for l of n items:
        yield l[i:i+n]
