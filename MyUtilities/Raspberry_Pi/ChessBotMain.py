import sys
import time
import RPi.GPIO as GPIO
import serial

import json

#Pins
turnBtn_pin = 7
GPIO.setmode(GPIO.BOARD)
GPIO.setup(turnBtn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#Coordinate Offsets
xOffset = 3.5 #[distance to start of board] + [distance to center of square (0.5)]
yOffset = 4.5
zOffset = -1

heightOffsets = [1,2,2,2,3,3] #[pawnHeight, rookHeight, knightHeight, bishopHeight, kingHeight, queenHeight]

xHome = 0 - xOffset
yHome = 0 - yOffset
zHome = 0 - zOffset

xGrave = 0.25 + 8 #The offset from the edge of the board to where the aiGrave begins.
yGrave = 0
zGrave = 0

def main():
        """This is the main program."""
        global gameOver, aiTurn

        #Setup
        gameOver = False
        aiTurn, boardState = startup()
        aiMove = "1111"

        while (gameOver == False): #While the game is still going on 
                while (aiTurn == False): #While it is not the AI's turn:
                        try:
                                lastBoardState, aiTurn = turnPlayer(boardState, aiMove)
                                        
                        except IOError:
                               print("\nError during player's turn.")

                #Now, it is the AI's turn.
                print("\nNow, it is my turn. Please move my piece as shown on the screen. Once you have done so, please press the button.")
                while (GPIO.input(turnBtn_pin) == True):
                        x = 1 #Do nothing
                print("Thank you.")
                
                #The AI program will change the text file. Once that file has changes, the AI has decided on it's move.
                #So now, the pi needs to find what the AI changed.
                notDifferent = True
                while (notDifferent):
                        time.sleep(0.5)
                        newBoardState = getState()
                        notDifferent, pieceFrom, pieceTo = checkBoard(lastBoardState, newBoardState)

                #Now it is the player's turn
                aiMove = getAiMove(newBoardState)
                #aiMove = str(pieceFrom[0] + 1) + str(pieceFrom[1] + 1) + str(pieceTo[0] + 1) + str(pieceTo[1] + 1)
                aiTurn = False

def getAiMove(boardState):
    """Determines what the AI's move was by looking at the changes in the file that the python chess program writes to"""
        aiMove = []
        for row in range(8):
                for col in range (8):
                        temp = boardState[row][col][0]
                        #print(temp)
                        if (temp == 'e'):
                                #print( "it was e")
                                aiMove.append("0")
                        elif (temp == 'b'):
                                #print("it was b")
                                aiMove.append("3")
                        elif (temp == 'w'):
                                #print( "it was w")
                                aiMove.append("4")
                        else:
                                print("\nAn error has occured in getAiMove")
                                print(temp)

        #print "aiMove: ", aiMove
        #print " "
        aiMove = ''.join(aiMove)
        return aiMove

def turnPlayer(boardState, aiMove):
        """This is the player's turn.

        Watch the input from the Arduino Mega. It will tell you the current board configuration. This may be done by watching for a button press.
        If the current configuration is not the same as last turn's configuration, then the player has moved."""

        print("It is now your turn. Press the button when you have made your move.")

        turnNotOver = True
        timerTicks = 0
        while (turnNotOver):
                timerTicks += 1
                #Wait for the player to push the turn button.
                buttonPressed, newBoardState, pieceTo, pieceFrom = listenBoard(boardState, aiMove)
                if (buttonPressed):
                        #Check that the player's move was valid.
                        valid = checkValid(newBoardState)
                        if (valid):
                               #print("Saving State...")
                                #If it is, Start the AI's Turn.
                                saveState(newBoardState, pieceTo, pieceFrom)
                                turnNotOver = False
                        else:
                                #If not, Tell the player to fix it. The monitor can show correct locations for that piece to the player.
                                print("\nYour move was invalid. Make a valid move please, and then press the button again.")

#                                         #If they wait for longer than about 5 seconds to push the button, display a reminder that they need to push the turn button to signify their turn is over.
#                if (timerTicks == 5000):
#                        print("Remember to push the button when your turn is over")
#                
#                #If the user takes a long time to decide what to do, do somthing such as intimidate them or tap on the table.
#                if (timerTicks == 30000):
#                        print("Foolish Human. I shall beat you!")
#                        tapOnTable()

        aiTurn = True
        return newBoardState, aiTurn

def turnAI(boardState):
        """Checks with the AI as to what its next move will be.

        boardState - The current board configuration matrix
        
        Example Input: turnAI(boardState)"""
        #Update the boardState for the pygame AI.
        #Recieve the newLayout of the board from the pygame AI.
        return newLayout

def startup():
        """The first things that happen before the game begins."""
        global gameOver, port, aiGrave, aiGraveCount

        #Get the current motor positions from the rotary switches.
        #Initialize serial connection
        try:
                port = serial.Serial("/dev/ttyACM0", 9600)
        except:
                port = serial.Serial("/dev/ttyACM1", 9600)
        #Reset Board File - Assume setup is correct.
        defaultBoard = [['bR', 'bT', 'bB', 'bQ', 'bK', 'bB', 'bT', 'bR'], 
                ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'], 
                ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], 
                ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], 
                ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], 
                ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], 
                ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'], 
                ['wR', 'wT', 'wB', 'wQ', 'wK', 'wB', 'wT', 'wR']]
        saveState(defaultBoard, [1,1], [1,1])
        boardState = getState()

        #Reset the AI's gravesite
        aiGrave =       [['e','e','e','e','e','e','e','e'],
                                ['e','e','e','e','e','e','e','e']]
        aiGraveCount = 0

        #Reset the Board arduino
        message = "reset"
        sendToArduino(message)

        #Request from the player who will go first.
        aiTurn = False #Hardcoded so that the player goes first.

        return aiTurn, boardState

def listenBoard(boardState, aiMove):
        """Listens to the ArduinoMega to get the current board configuration.

        aiMove - A string in the form of [pieceTo][pieceFrom].
        
        Example Input: listenBoard(boardState, "1234") """
        buttonPressed = False
        newBoardState = -1
        pieceTo = [1,1]
        pieceFrom = [1,1]

        #Is the button pressed?
        if (GPIO.input(turnBtn_pin) == False): #It is false when the button is pressed.
               #print("button pressed")
                #If so, then get current board state
                #sendToArduino("1:" + aiMove)
                sendToArduino(aiMove)
                
                message = getFromArduino()
               #print(message)
                pieceFrom, pieceTo, taken = parseMessage(message)

               #print("taken: ")
              #print(taken)
                if (taken != -1):
                        buttonPressed = True
                        if (taken == "K"):
                                newBoardState = changeState(boardState, [8,5], [8,7])
                                newBoardState = changeState(newBoardState, [8,8], [8,6])
                        elif (taken == "Q"):
                                newBoardState = changeState(boardState, [8,5], [8,3])
                                newBoardState = changeState(newBoardState, [8,1], [8,4])
                        else:
                                newBoardState = changeState(boardState, pieceFrom, pieceTo)
                else:
                        print("\nYou need to move a piece before pressing the button.")
                #If not, do nothing.

               #print ("\nnewBoardState:\n\t")
               #print (newBoardState)
        return buttonPressed, newBoardState, pieceTo, pieceFrom

def parseMessage(message):
        """Interprets the message sent by the arduino as 'pieceFrom' and 'pieceTo'."""

        if (message[0] != "n"):
                if (message[4] == "Q"): #Queen-side castleing
                        print("Queen-side Castle")
                        pieceFrom = [0,0]
                        pieceTo = [0,0]
                        taken = "Q"
                elif (message[4] == "K"): #King-side castleing
                        print("King-side Castle")
                        pieceFrom = [0,0]
                        pieceTo = [0,0]
                        taken = "K"
                else:
                        pieceFrom = [int(message[0]), int(message[1])]
                        pieceTo = [int(message[2]), int(message[3])]
                        taken = int(message[4])
        else:
                pieceFrom = [0,0]
                pieceTo = [0,0]
                taken = -1

        return [pieceFrom, pieceTo, taken]

def checkValid(boardState):
        """Sends the boardState to a portion of the chessAI, which will determine if the move is valid or not.
        It does this by writing to a file to check it out.
        If it is not a valid move, the chessAI will write its response to the file.
        If it is valid, then the chessAI will move on with teh AI's turn.
        """

        #For now, we are assuming a perfect game.
        return True

def checkBoard(lastBoardState, newBoardState):
        """Checks if the current board state is different from last turn's board state.

        lastBoardState - The configuration of the board last turn.
        newBoardState - The configuration of the board this turn.

        Example Input: checkBoard(boardState, newBoardState)"""

        pieceFrom = [1,1]
        pieceTo = [1,1]

        if (lastBoardState != newBoardState):

                #Find the first discrepancy, and the second discrepancy
                count = 0
                for row in range(8):
                        for col in range(8):
                                if (lastBoardState[row][col] != newBoardState[row][col]):
                                        count += 1
                                        if (count == 1):
                                                firstRow = row
                                                firstCol = col
                                        else:
                                                secondRow = row
                                                secondCol = col
                                                break
                        if (count == 2):
                                break

                #Determine How to move the pieces
                if (newBoardState[firstRow][firstCol] == "e"): #Check movement down the board
                       #print "A piece was moved down from first to second"
                        pieceFrom = [firstRow, firstCol]
                        pieceTo = [secondRow, secondCol]

                        if (lastBoardState[secondRow][secondCol] != "e"):
                               #print "A piece was taken before it moved"
                                if (lastBoardState[secondRow][secondCol] == "wK"):
                                       #print "The piece that was taken was the king"
                                        takeKing(lastBoardState, pieceTo)
                                else:
                                        hi = 1
                                       #print "The piece thatw as taken was not the king"
                                        #moveToGraveyard(lastBoardState, pieceTo)

                elif (newBoardState[secondRow][secondCol] == "e"): #Check movement up the board
                       #print "A piece was moved up from second to first"
                        pieceFrom = [secondRow, secondCol]
                        pieceTo = [firstRow, firstCol]

                        if (lastBoardState[firstRow][firstCol] != "e"):
                               #print "A piece was taken before it moved"
                                if (lastBoardState[first][first] == "wK"):
                                       #print "The piece that was taken was the king"
                                        takeKing(lastBoardState, pieceTo)
                                else:
                                        hi = 1
                                       #print "The piece that was taken was not the king"
                                        #moveToGraveyard(lastBoardState, pieceTo)

                else: #There was an error, becaus eno difference should have been found.
                       #print("There was an error in finding what move the AI made.")
                        gameOver = True
                        return True, pieceFrom, pieceTo

               #print "I moved from ", pieceFrom
               #print "to ", pieceTo
                movePiece(newBoardState, pieceFrom, pieceTo)

                return False, pieceFrom, pieceTo
        return True, pieceFrom, pieceTo

def getState():
        """Loads the current board state from the file."""
        with open('currentBoardState') as json_file:
                boardState = json.load(json_file)
        return boardState

def saveState(boardState, pieceTo, pieceFrom):
        """Saves the new board state to the file."""

        pieceTo[0] -= 1
        pieceTo[1] -= 1
        pieceFrom[0] -= 1
        pieceFrom[1] -= 1
        with open('toAndFrom', 'w') as json_file:
                json.dump([pieceFrom, pieceTo], json_file)
        
        with open('currentBoardState', 'w') as json_file:
                json.dump(boardState, json_file)

def debugBoardState():
        """ A debug run for testing the board states."""
        #Reset Board
        defaultBoard = [['bR', 'bT', 'bB', 'bQ', 'bK', 'bB', 'bT', 'bR'], ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'], ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], ['e', 'e', 'e', 'e', 'e', 'e', 'e', 'e'], ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'], ['wR', 'wT', 'wB', 'wQ', 'wK', 'wB', 'wT', 'wR']]
        saveState(defaultBoard, [1,7],[1,8])

        #Load reset board
        boardState = getState()
       #print(boardState)

        #Change board
        boardState = changeState(boardState,(1,3),(3,3))

        #Save Changes
        saveState(boardState,[3,3],[3,1])

        #Confirm Changes
        boardState = getState()
       #print(boardState)

def changeState(boardState, piece, destination):
        """Changes the current board state.

        boardState - The current board configuration matrix.
        piece - A tuple of which cell is being moved.
        destination - A tuple of which cell the piece is being moved to.

        Example Input: changeState(boardState, (3,3), (4,3)"""
       #print("Changing State...")
       #print("piece:")
       #print(piece)
       #print("destination:")
       #print(destination)

       #print("\n")
       #print(boardState[destination[0] - 1][destination[1] - 1])
       #print(boardState[piece[0] - 1][piece[1] - 1])

        temp =  boardState[destination[0] - 1][destination[1] - 1]
        boardState[destination[0] - 1][destination[1] - 1] = boardState[piece[0] - 1][piece[1] - 1]
        boardState[piece[0] - 1][piece[1] - 1] = temp

        return boardState

def coordToInch(x, y, z):
        """Converts board corrdinates to inches, which is what the arm uses.
        Each square is exactly 1 inch apart, and the top left square is nammed 1-1 so the only change that needs
        to be made is an offset for the arm's position.

        x - the x-coordinate
        y - the y-coordinate
        z - the z-coordinate

        Example Input: coordToInch(1, 2, 3)"""

        x += xOffset
        y += yOffset
        z += zOffset

        return x, y, z

def whichPiece(boardState, piece):
        """Determines what kind of piece is on the board at the loaction given.

        Pawn:   0
        Rook:   1
        Knight: 2
        Bishop: 3
        King:   4
        Queen:  5
        
        Example Input: whichPiece([1,2])"""

       #print "piece: ", piece
       #print boardState[piece[0]][piece[1]]
        #print boardState[piece[0]][piece[1]][1]
        piece = boardState[piece[0]][piece[1]]#[1]
       #print piece[1]
        piece = piece[1]

        if (piece != "e"):
                if (piece == 'P'):
                       #print "It was a pawn"
                        which = 0
                elif (piece == 'R'):
                       #print "It was a Rook"
                        which = 1
                elif (piece == 'T'):
                       #print "It was a Knight"
                        which = 2
                elif (piece == 'B'):
                       #print "It was a Bishop"
                        which = 3
                elif (piece == 'Q'):
                       #print "It was a Queen"
                        which = 4
                elif (piece == 'K'):
                       #print "It was a King"
                        which = 5
                else:
                       #print "It was a ???"
                        which = -1
        else:
               #print "It was an empty space"
                which = -1

        return which

def offsetPiece(z, piece):
        """Modifies the z inches to take in account the piece height.

        z - The z-inches
        which - The piece as shown on the boardState

        Example Input: offsetPiece(3, 'bR')"""

        which = 0# whichPiece(boardState, piece)
        z += heightOffsets[which]

        return z

def movePiece(boardState, piece, destination):
        """Moves the AI's piece to a new location.

        destination - The new spot for the piece. The first number is the row, second is the column.
        which - The letter for the piece to be moved.
        boardState - The current board configuration matrix.

        Example Input: movePiece(boardState, [1,2],[3,4])"""
        #pick up the piece.
        #pickUpPiece(boardState,piece)

        #Put the piece down.
        #putDownPiece(boardState,destination)

        #Move out of the way.
        #goHome()
        return   

def goHome():
        """Moves the arm to the home position"""

        message = "0:" + str(xHome) + ":" + str(yHome) + ":" + str(zHome) + ":0" 
        #sendToArduino(message)

def moveToGraveyard(boardState, piece):
        """Moves the player's piece to the graveyard. The player moves the AI's pieces on their own.

        boardState - The current board configuration matrix
        piece - The row and column of the piece to move. [row,col]

        Example Input: moveToGraveyard(boardState, piece)"""
        global aiGrave, aiGraveCount

       #print piece
        
        #Pick up the piece to move to the grave yard
        pickUpPiece(boardState, piece)

        #Calculate which graveyard square
        #Increment where the grave is.
        aiGraveCount += 1
        row = piece[0] + xGrave
        col = piece[1] + yGrave

        which = whichPiece(boardState, piece)

        #Pawn: Entire first row
        if (which == 0):
                for i in range(8):
                        if (aiGrave[0][i] == 'e'):
                                pieceTo = [row, col*(i + 1)]
                                break

        #Rook: Slots 0 and 7
        elif (which == 1):
                if (aiGrave[1][0] == 'e'):
                        pieceTo = [row, col + 0]
                else:
                        pieceTo = [row, col + 7]

        #Knight: Slots 1 and 6
        elif (which == 1):
                if (aiGrave[1][0] == 'e'):
                        pieceTo = [row, col + 1]
                else:
                        pieceTo = [row, col + 6]
        
        #Bishop: Slots 2 and 5
        elif (which == 1):
                if (aiGrave[1][0] == 'e'):
                        pieceTo = [row, col + 2]
                else:
                        pieceTo = [row, col + 5]

        #King: Slot 3
        elif (which == 1):
                pieceTo = [row, col + 3]

        #Queen: Slot 4
        elif (which == 1):
                pieceTo = [row, col + 4]


        #Move it to that graveyard square
        putDownPiece(boardState, pieceTo)

        return

def pickUpPiece(boardState, spot):
        """Picks up a piece.

        boardState - The current board configuration matrix
        spot - The board coordinates for the piece to pieck up
        
        Example Input: pickUpPiece(boardState, [1,2])"""
        y = spot[0] #Row
        x = spot[1] #Column
        z = 0

        #print "Spot: ", boardState[spot[0]][spot[1]]
        #Look up which which of piece it is (This will tell it how far down it needs to go)
        which = 0# boardState[spot[0]][spot[1]]
        offsetPiece(zOffset,which)

        #Move to the spot with the claw open. Pick it up, and go to home.
#       message = "0:" + str(xOffset + x) + ":" + str(yOffset + y) + ":" + str(zOffset + z) + ":1"
#       sendToArduino(message)

        return

def putDownPiece(boardState,spot):
        """Puts down a piece.

        which - The letter for the piece to be moved.

        Example Input: putDownPiece(boardState, [3,4])"""
        y = spot[0] #Row
        x = spot[1] #Column
        z = 0

        #Look up which which of piece it is (This will tell it how far down it needs to go)
        which = 0 #boardState[spot[0]][spot[1]]
        #which = which[1]
        offsetPiece(zOffset,which)

        #Move to the spot with the claw closed. Put it down, and go to home.
#       message = "0:" + str(xOffset + x) + ":" + str(yOffset + y) + ":" + str(zOffset + z) + ":0"
#       sendToArduino(message)

        return

def castling(rook, boardState):
        """ astles a king and rook.

        rook - the letter for which rook.
        boardState - The current board configuration matrix
        
        Example Input: castling(R1, boardState)"""

        #For now, the AI does not castle.

        #Move Rook to Midway Point
        #Move the king to the rook's original location
        #Move the rook in teh midway point to the king's location.
        return

def takeKing(boardState, piece):
        """When the arm is going to take the player's king. Instead of picking it up, it is going to knowck it over.

        boardState - The current board configuration matrix
        
        Example Input: takeKing(boardState)"""
        global gameOver

        #For now, take the king like normal.
        #moveToGraveyard(boardState, piece)
        gameOver = True

        #Look up the motor coodinates for the piece.
        #Move the motors to just before that location.
        #rotate the wrist up.
        #Say the game is over.
        #Move back to home.

def intimidatePlayer():
        """Opens the hand menaceingly at the player if they take too long to think and the AI is winning."""
        #Extend the arm a bit.
        #Rotate the wrist so the claw is facing the player.
        #Open and close the claw while rocking back and forth a tiny bit.
        #Go back to home
        return

def tapOnTable():
        """Taps on the table if the player is taking too long to think and the AI is loseing."""
        #Rotate teh base to the side.
        #Move the arm up and down slightly.
        return

def sendToArduino(message):
        """This sends a string message to the arduino using serial

        The arm needs a string like this: "0:1:2:2:0" Which is parsed as:
        "[0 for arm, 1 for board]:[x]:[y]:[z]:[0] for open, 1 for closed]"

        The board needs a string like this: "1:2345" Which is parsed as:
        "[0 for arm, 1 for board]:[[pieceFrom][pieceTo]]" """

        global port
       #print(message)
        port.write(message)

def getFromArduino():
        """This recieves a string message from the arduino using serial."""
        global port
        message = port.readline()
        return message

main()
#debugBoardState()
