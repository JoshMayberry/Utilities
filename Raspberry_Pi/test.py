import json

data = [['bR','bT','bB','bQ','bK','bB','bT','bR'],
['bP','bP','bP','bP','bP','bP','bP','bP'],
['e','e','e','e','e','e','e','e'],
['e','e','e','e','e','e','e','e'],
['e','e','e','e','e','e','e','e'],
['e','e','e','e','e','e','e','e'],
['wP','wP','wP','wP','wP','wP','wP','wP'],
['wR','wT','wB','wQ','wK','wB','wT','wR']]

#Save
with open('currentBoardState','w') as outfile:
    json.dump(data, outfile)

#Load
with open('currentBoardState') as json_file:
    json_data = json.load(json_file)
    print(json_data)
