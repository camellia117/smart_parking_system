def recommend(user_location, parking_lots):

    best_lot = None

    best_score = 9999

    for lot in parking_lots:

        distance = lot["distance"]

        price = lot["price"]

        score = distance*0.7 + price*0.3

        if score < best_score:

            best_score = score

            best_lot = lot

    return best_lot