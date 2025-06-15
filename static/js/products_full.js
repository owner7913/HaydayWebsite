const products = [
  {
    "product": "Wheat",
    "machine": "Crops",
    "level": 1,
    "price": 3,
    "time_min": 2,
    "xp": 1,
    "profit_per_hour": 90.0,
    "xp_per_hour": 30.0
  },
  {
    "product": "Corn",
    "machine": "Crops",
    "level": 2,
    "price": 7,
    "time_min": 5,
    "xp": 1,
    "profit_per_hour": 84.0,
    "xp_per_hour": 12.0
  },
  {
    "product": "Soybean",
    "machine": "Crops",
    "level": 5,
    "price": 10,
    "time_min": 20,
    "xp": 2,
    "profit_per_hour": 30.0,
    "xp_per_hour": 6.0
  },
  {
    "product": "Sugarcane",
    "machine": "Crops",
    "level": 7,
    "price": 14,
    "time_min": 30,
    "xp": 3,
    "profit_per_hour": 28.0,
    "xp_per_hour": 6.0
  },
  {
    "product": "Carrot",
    "machine": "Crops",
    "level": 9,
    "price": 7,
    "time_min": 10,
    "xp": 2,
    "profit_per_hour": 42.0,
    "xp_per_hour": 12.0
  },
  {
    "product": "Indigo",
    "machine": "Crops",
    "level": 13,
    "price": 25,
    "time_min": 120,
    "xp": 5,
    "profit_per_hour": 12.5,
    "xp_per_hour": 2.5
  },
  {
    "product": "Pumpkin",
    "machine": "Crops",
    "level": 15,
    "price": 32,
    "time_min": 180,
    "xp": 6,
    "profit_per_hour": 10.66666667,
    "xp_per_hour": 2.0
  },
  {
    "product": "Cotton",
    "machine": "Crops",
    "level": 18,
    "price": 28,
    "time_min": 150,
    "xp": 6,
    "profit_per_hour": 11.2,
    "xp_per_hour": 2.4
  },
  {
    "product": "Chili pepper",
    "machine": "Crops",
    "level": 25,
    "price": 36,
    "time_min": 240,
    "xp": 4,
    "profit_per_hour": 9.0,
    "xp_per_hour": 1.0
  },
  {
    "product": "Tomato",
    "machine": "Crops",
    "level": 30,
    "price": 43,
    "time_min": 360,
    "xp": 8,
    "profit_per_hour": 7.166666667,
    "xp_per_hour": 1.333333333
  },
  {
    "product": "Strawberry",
    "machine": "Crops",
    "level": 34,
    "price": 50,
    "time_min": 480,
    "xp": 10,
    "profit_per_hour": 6.25,
    "xp_per_hour": 1.25
  },
  {
    "product": "Potato",
    "machine": "Crops",
    "level": 35,
    "price": 36,
    "time_min": 220,
    "xp": 7,
    "profit_per_hour": 9.818181818,
    "xp_per_hour": 1.909090909
  },
  {
    "product": "Sesame",
    "machine": "Crops",
    "level": 50,
    "price": 18,
    "time_min": 60,
    "xp": 4,
    "profit_per_hour": 18.0,
    "xp_per_hour": 4.0
  },
  {
    "product": "Pineapple",
    "machine": "Crops",
    "level": 52,
    "price": 14,
    "time_min": 30,
    "xp": 3,
    "profit_per_hour": 28.0,
    "xp_per_hour": 6.0
  },
  {
    "product": "Lily",
    "machine": "Crops",
    "level": 53,
    "price": 21,
    "time_min": 90,
    "xp": 5,
    "profit_per_hour": 14.0,
    "xp_per_hour": 3.333333333
  },
  {
    "product": "Rice",
    "machine": "Crops",
    "level": 56,
    "price": 18,
    "time_min": 45,
    "xp": 3,
    "profit_per_hour": 24.0,
    "xp_per_hour": 4.0
  },
  {
    "product": "Lettuce",
    "machine": "Crops",
    "level": 58,
    "price": 32,
    "time_min": 210,
    "xp": 7,
    "profit_per_hour": 9.142857143,
    "xp_per_hour": 2.0
  },
  {
    "product": "Garlic",
    "machine": "Crops",
    "level": 60,
    "price": 14,
    "time_min": 30,
    "xp": 3,
    "profit_per_hour": 28.0,
    "xp_per_hour": 6.0
  },
  {
    "product": "Sunflower",
    "machine": "Crops",
    "level": 63,
    "price": 21,
    "time_min": 90,
    "xp": 5,
    "profit_per_hour": 14.0,
    "xp_per_hour": 3.333333333
  },
  {
    "product": "Cabbage",
    "machine": "Crops",
    "level": 65,
    "price": 18,
    "time_min": 45,
    "xp": 3,
    "profit_per_hour": 24.0,
    "xp_per_hour": 4.0
  },
  {
    "product": "Onion",
    "machine": "Crops",
    "level": 68,
    "price": 39,
    "time_min": 300,
    "xp": 8,
    "profit_per_hour": 7.8,
    "xp_per_hour": 1.6
  },
  {
    "product": "Cucumber",
    "machine": "Crops",
    "level": 70,
    "price": 14,
    "time_min": 35,
    "xp": 3,
    "profit_per_hour": 24.0,
    "xp_per_hour": 5.142857143
  },
  {
    "product": "Beetroot",
    "machine": "Crops",
    "level": 72,
    "price": 14,
    "time_min": 40,
    "xp": 3,
    "profit_per_hour": 21.0,
    "xp_per_hour": 4.5
  },
  {
    "product": "Bell pepper",
    "machine": "Crops",
    "level": 74,
    "price": 36,
    "time_min": 270,
    "xp": 7,
    "profit_per_hour": 8.0,
    "xp_per_hour": 1.555555556
  },
  {
    "product": "Ginger​​​​",
    "machine": "Crops",
    "level": 78,
    "price": 28,
    "time_min": 150,
    "xp": 6,
    "profit_per_hour": 11.2,
    "xp_per_hour": 2.4
  },
  {
    "product": "Tea leaf",
    "machine": "Crops",
    "level": 80,
    "price": 43,
    "time_min": 390,
    "xp": 9,
    "profit_per_hour": 6.615384615,
    "xp_per_hour": 1.384615385
  },
  {
    "product": "Peony",
    "machine": "Crops",
    "level": 82,
    "price": 36,
    "time_min": 240,
    "xp": 7,
    "profit_per_hour": 9.0,
    "xp_per_hour": 1.75
  },
  {
    "product": "Broccoli",
    "machine": "Crops",
    "level": 83,
    "price": 21,
    "time_min": 90,
    "xp": 4,
    "profit_per_hour": 14.0,
    "xp_per_hour": 2.666666667
  },
  {
    "product": "Grapes",
    "machine": "Crops",
    "level": 84,
    "price": 32,
    "time_min": 180,
    "xp": 6,
    "profit_per_hour": 10.66666667,
    "xp_per_hour": 2.0
  },
  {
    "product": "Mint",
    "machine": "Crops",
    "level": 85,
    "price": 32,
    "time_min": 180,
    "xp": 6,
    "profit_per_hour": 10.66666667,
    "xp_per_hour": 2.0
  },
  {
    "product": "Passion fruit",
    "machine": "Crops",
    "level": 88,
    "price": 18,
    "time_min": 60,
    "xp": 4,
    "profit_per_hour": 18.0,
    "xp_per_hour": 4.0
  },
  {
    "product": "Mushroom",
    "machine": "Crops",
    "level": 89,
    "price": 10,
    "time_min": 20,
    "xp": 2,
    "profit_per_hour": 30.0,
    "xp_per_hour": 6.0
  },
  {
    "product": "Eggplant",
    "machine": "Crops",
    "level": 90,
    "price": 14,
    "time_min": 40,
    "xp": 3,
    "profit_per_hour": 21.0,
    "xp_per_hour": 4.5
  },
  {
    "product": "Watermelon",
    "machine": "Crops",
    "level": 92,
    "price": 39,
    "time_min": 300,
    "xp": 8,
    "profit_per_hour": 7.8,
    "xp_per_hour": 1.6
  },
  {
    "product": "Clay",
    "machine": "Crops",
    "level": 94,
    "price": 18,
    "time_min": 110,
    "xp": 5,
    "profit_per_hour": 9.818181818,
    "xp_per_hour": 2.727272727
  },
  {
    "product": "Chickpea",
    "machine": "Crops",
    "level": 95,
    "price": 18,
    "time_min": 60,
    "xp": 4,
    "profit_per_hour": 18.0,
    "xp_per_hour": 4.0
  },
  {
    "product": "Apple",
    "machine": "Trees & Bushes",
    "level": 15,
    "price": 39,
    "time_min": 960,
    "xp": 7,
    "profit_per_hour": 22.175,
    "xp_per_hour": 0.4375
  },
  {
    "product": "Raspberry",
    "machine": "Trees & Bushes",
    "level": 19,
    "price": 46,
    "time_min": 1080,
    "xp": 9,
    "profit_per_hour": 21.57777778,
    "xp_per_hour": 0.5
  },
  {
    "product": "Cherry",
    "machine": "Trees & Bushes",
    "level": 22,
    "price": 68,
    "time_min": 1620,
    "xp": 13,
    "profit_per_hour": 17.74814815,
    "xp_per_hour": 0.4814814815
  },
  {
    "product": "Blackberry",
    "machine": "Trees & Bushes",
    "level": 26,
    "price": 82,
    "time_min": 1920,
    "xp": 16,
    "profit_per_hour": 17.075,
    "xp_per_hour": 0.5
  },
  {
    "product": "Cacao",
    "machine": "Trees & Bushes",
    "level": 36,
    "price": 86,
    "time_min": 2040,
    "xp": 16,
    "profit_per_hour": 16.85882353,
    "xp_per_hour": 0.4705882353
  },
  {
    "product": "Honeycomb",
    "machine": "Trees & Bushes",
    "level": 39,
    "price": 68,
    "time_min": 35,
    "xp": 8,
    "profit_per_hour": 109.7142857,
    "xp_per_hour": 13.71428571
  },
  {
    "product": "Coffee",
    "machine": "Trees & Bushes",
    "level": 42,
    "price": 64,
    "time_min": 1500,
    "xp": 12,
    "profit_per_hour": 18.696,
    "xp_per_hour": 0.48
  },
  {
    "product": "Olive",
    "machine": "Trees & Bushes",
    "level": 57,
    "price": 82,
    "time_min": 1440,
    "xp": 17,
    "profit_per_hour": 19.01666667,
    "xp_per_hour": 0.7083333333
  },
  {
    "product": "Lemon",
    "machine": "Trees & Bushes",
    "level": 66,
    "price": 93,
    "time_min": 1740,
    "xp": 18,
    "profit_per_hour": 18.85517241,
    "xp_per_hour": 0.6206896552
  },
  {
    "product": "Orange",
    "machine": "Trees & Bushes",
    "level": 71,
    "price": 97,
    "time_min": 1860,
    "xp": 19,
    "profit_per_hour": 17.53548387,
    "xp_per_hour": 0.6129032258
  },
  {
    "product": "Peach",
    "machine": "Trees & Bushes",
    "level": 76,
    "price": 100,
    "time_min": 1800,
    "xp": 20,
    "profit_per_hour": 18.68,
    "xp_per_hour": 0.6666666667
  },
  {
    "product": "Banana",
    "machine": "Trees & Bushes",
    "level": 88,
    "price": 104,
    "time_min": 1620,
    "xp": 20,
    "profit_per_hour": 20.63703704,
    "xp_per_hour": 0.7407407407
  },
  {
    "product": "Plum",
    "machine": "Trees & Bushes",
    "level": 94,
    "price": 82,
    "time_min": 1620,
    "xp": 16,
    "profit_per_hour": 17.64444444,
    "xp_per_hour": 0.5925925926
  },
  {
    "product": "Mango",
    "machine": "Trees & Bushes",
    "level": 97,
    "price": 100,
    "time_min": 1920,
    "xp": 20,
    "profit_per_hour": 16.8875,
    "xp_per_hour": 0.625
  },
  {
    "product": "Coconut",
    "machine": "Trees & Bushes",
    "level": 101,
    "price": 108,
    "time_min": 2160,
    "xp": 21,
    "profit_per_hour": 16.5,
    "xp_per_hour": 0.5833333333
  },
  {
    "product": "Guava",
    "machine": "Trees & Bushes",
    "level": 104,
    "price": 111,
    "time_min": 2040,
    "xp": 22,
    "profit_per_hour": 17.37647059,
    "xp_per_hour": 0.6470588235
  },
  {
    "product": "Egg",
    "machine": "Animal Products",
    "level": 1,
    "price": 18,
    "time_min": 20,
    "xp": 2,
    "profit_per_hour": 33.0,
    "xp_per_hour": 6.0
  },
  {
    "product": "Milk",
    "machine": "Animal Products",
    "level": 6,
    "price": 32,
    "time_min": 60,
    "xp": 3,
    "profit_per_hour": 18.0,
    "xp_per_hour": 3.0
  },
  {
    "product": "Bacon",
    "machine": "Animal Products",
    "level": 10,
    "price": 50,
    "time_min": 240,
    "xp": 5,
    "profit_per_hour": -2.5,
    "xp_per_hour": 1.25
  },
  {
    "product": "Wool",
    "machine": "Animal Products",
    "level": 16,
    "price": 54,
    "time_min": 360,
    "xp": 5,
    "profit_per_hour": -0.8333333333,
    "xp_per_hour": 0.8333333333
  },
  {
    "product": "Goat milk",
    "machine": "Animal Products",
    "level": 32,
    "price": 64,
    "time_min": 480,
    "xp": 6,
    "profit_per_hour": -1.25,
    "xp_per_hour": 0.75
  },
  {
    "product": "Chicken feed",
    "machine": "Feed Mill",
    "level": 3,
    "price": 7,
    "time_min": 4,
    "xp": 1,
    "profit_per_hour": 112.9411765,
    "xp_per_hour": 14.11764706
  },
  {
    "product": "Cow feed",
    "machine": "Feed Mill",
    "level": 6,
    "price": 14,
    "time_min": 8,
    "xp": 2,
    "profit_per_hour": 105.8823529,
    "xp_per_hour": 14.11764706
  },
  {
    "product": "Pig feed",
    "machine": "Feed Mill",
    "level": 10,
    "price": 14,
    "time_min": 17,
    "xp": 2,
    "profit_per_hour": 63.52941176,
    "xp_per_hour": 7.058823529
  },
  {
    "product": "Sheep feed",
    "machine": "Feed Mill",
    "level": 16,
    "price": 14,
    "time_min": 25,
    "xp": 3,
    "profit_per_hour": 54.11764706,
    "xp_per_hour": 7.058823529
  },
  {
    "product": "Goat feed",
    "machine": "Feed Mill",
    "level": 32,
    "price": 14,
    "time_min": 34,
    "xp": 3,
    "profit_per_hour": 31.76470588,
    "xp_per_hour": 5.294117647
  },
  {
    "product": "Wheat bundle",
    "machine": "Feed Mill",
    "level": 34,
    "price": 50,
    "time_min": 76,
    "xp": 10,
    "profit_per_hour": -58.82352941,
    "xp_per_hour": 7.843137255
  },
  {
    "product": "Meat bucket",
    "machine": "Feed Mill",
    "level": 34,
    "price": 72,
    "time_min": 38,
    "xp": 15,
    "profit_per_hour": 29.80392157,
    "xp_per_hour": 23.52941176
  },
  {
    "product": "Bread",
    "machine": "Bakery",
    "level": 2,
    "price": 21,
    "time_min": 4,
    "xp": 3,
    "profit_per_hour": 169.4117647,
    "xp_per_hour": 42.35294118
  },
  {
    "product": "Corn bread",
    "machine": "Bakery",
    "level": 7,
    "price": 72,
    "time_min": 25,
    "xp": 8,
    "profit_per_hour": 51.76470588,
    "xp_per_hour": 18.82352941
  },
  {
    "product": "Cookie",
    "machine": "Bakery",
    "level": 10,
    "price": 104,
    "time_min": 51,
    "xp": 13,
    "profit_per_hour": 35.29411765,
    "xp_per_hour": 15.29411765
  },
  {
    "product": "Raspberry muffin",
    "machine": "Bakery",
    "level": 19,
    "price": 140,
    "time_min": 38,
    "xp": 17,
    "profit_per_hour": 37.64705882,
    "xp_per_hour": 26.66666667
  },
  {
    "product": "Blackberry muffin",
    "machine": "Bakery",
    "level": 26,
    "price": 226,
    "time_min": 38,
    "xp": 27,
    "profit_per_hour": 36.07843137,
    "xp_per_hour": 42.35294118
  },
  {
    "product": "Pizza",
    "machine": "Bakery",
    "level": 33,
    "price": 190,
    "time_min": 12,
    "xp": 23,
    "profit_per_hour": 89.41176471,
    "xp_per_hour": 108.2352941
  },
  {
    "product": "Spicy pizza",
    "machine": "Bakery",
    "level": 37,
    "price": 226,
    "time_min": 12,
    "xp": 27,
    "profit_per_hour": 89.41176471,
    "xp_per_hour": 127.0588235
  },
  {
    "product": "Potato bread",
    "machine": "Bakery",
    "level": 39,
    "price": 284,
    "time_min": 38,
    "xp": 34,
    "profit_per_hour": 40.78431373,
    "xp_per_hour": 53.33333333
  },
  {
    "product": "Frutti di Mare pizza",
    "machine": "Bakery",
    "level": 45,
    "price": 403,
    "time_min": 12,
    "xp": 48,
    "profit_per_hour": 94.11764706,
    "xp_per_hour": 225.8823529
  },
  {
    "product": "Gingerbread cookie",
    "machine": "Bakery",
    "level": 86,
    "price": 273,
    "time_min": 25,
    "xp": 33,
    "profit_per_hour": 70.58823529,
    "xp_per_hour": 77.64705882
  },
  {
    "product": "Banana bread",
    "machine": "Bakery",
    "level": 91,
    "price": 424,
    "time_min": 25,
    "xp": 50,
    "profit_per_hour": 49.41176471,
    "xp_per_hour": 117.6470588
  },
  {
    "product": "Macaroon",
    "machine": "Bakery",
    "level": 101,
    "price": 421,
    "time_min": 30,
    "xp": 50,
    "profit_per_hour": 38.0,
    "xp_per_hour": 100.0
  },
  {
    "product": "Cream",
    "machine": "Dairy",
    "level": 6,
    "price": 50,
    "time_min": 17,
    "xp": 6,
    "profit_per_hour": 63.52941176,
    "xp_per_hour": 21.17647059
  },
  {
    "product": "Butter",
    "machine": "Dairy",
    "level": 9,
    "price": 82,
    "time_min": 25,
    "xp": 10,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 23.52941176
  },
  {
    "product": "Cheese",
    "machine": "Dairy",
    "level": 12,
    "price": 122,
    "time_min": 51,
    "xp": 15,
    "profit_per_hour": 30.58823529,
    "xp_per_hour": 17.64705882
  },
  {
    "product": "Goat cheese",
    "machine": "Dairy",
    "level": 33,
    "price": 162,
    "time_min": 76,
    "xp": 19,
    "profit_per_hour": 26.66666667,
    "xp_per_hour": 14.90196078
  },
  {
    "product": "Brown sugar",
    "machine": "Sugar Mill",
    "level": 7,
    "price": 32,
    "time_min": 17,
    "xp": 4,
    "profit_per_hour": 63.52941176,
    "xp_per_hour": 14.11764706
  },
  {
    "product": "White sugar",
    "machine": "Sugar Mill",
    "level": 13,
    "price": 50,
    "time_min": 34,
    "xp": 6,
    "profit_per_hour": 38.82352941,
    "xp_per_hour": 10.58823529
  },
  {
    "product": "Syrup",
    "machine": "Sugar Mill",
    "level": 18,
    "price": 90,
    "time_min": 76,
    "xp": 11,
    "profit_per_hour": 26.66666667,
    "xp_per_hour": 8.62745098
  },
  {
    "product": "Popcorn",
    "machine": "Popcorn Pot",
    "level": 8,
    "price": 32,
    "time_min": 25,
    "xp": 4,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 9.411764706
  },
  {
    "product": "Buttered popcorn",
    "machine": "Popcorn Pot",
    "level": 16,
    "price": 126,
    "time_min": 51,
    "xp": 15,
    "profit_per_hour": 35.29411765,
    "xp_per_hour": 17.64705882
  },
  {
    "product": "Chili popcorn",
    "machine": "Popcorn Pot",
    "level": 25,
    "price": 122,
    "time_min": 102,
    "xp": 15,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 8.823529412
  },
  {
    "product": "Honey popcorn",
    "machine": "Popcorn Pot",
    "level": 40,
    "price": 360,
    "time_min": 76,
    "xp": 43,
    "profit_per_hour": 29.80392157,
    "xp_per_hour": 33.7254902
  },
  {
    "product": "Chocolate popcorn",
    "machine": "Popcorn Pot",
    "level": 44,
    "price": 248,
    "time_min": 127,
    "xp": 29,
    "profit_per_hour": 29.17647059,
    "xp_per_hour": 13.64705882
  },
  {
    "product": "Snack mix",
    "machine": "Popcorn Pot",
    "level": 64,
    "price": 309,
    "time_min": 38,
    "xp": 50,
    "profit_per_hour": 67.45098039,
    "xp_per_hour": 78.43137255
  },
  {
    "product": "Pancake",
    "machine": "BBQ Grill",
    "level": 9,
    "price": 108,
    "time_min": 25,
    "xp": 13,
    "profit_per_hour": 51.76470588,
    "xp_per_hour": 30.58823529
  },
  {
    "product": "Bacon and eggs",
    "machine": "BBQ Grill",
    "level": 11,
    "price": 201,
    "time_min": 51,
    "xp": 24,
    "profit_per_hour": 34.11764706,
    "xp_per_hour": 28.23529412
  },
  {
    "product": "Hamburger",
    "machine": "BBQ Grill",
    "level": 18,
    "price": 180,
    "time_min": 102,
    "xp": 22,
    "profit_per_hour": 22.35294118,
    "xp_per_hour": 12.94117647
  },
  {
    "product": "Fish burger",
    "machine": "BBQ Grill",
    "level": 27,
    "price": 226,
    "time_min": 102,
    "xp": 27,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 15.88235294
  },
  {
    "product": "Roasted tomatoes",
    "machine": "BBQ Grill",
    "level": 30,
    "price": 118,
    "time_min": 76,
    "xp": 14,
    "profit_per_hour": 25.09803922,
    "xp_per_hour": 10.98039216
  },
  {
    "product": "Baked potato",
    "machine": "BBQ Grill",
    "level": 35,
    "price": 298,
    "time_min": 29,
    "xp": 36,
    "profit_per_hour": 36.30252101,
    "xp_per_hour": 72.60504202
  },
  {
    "product": "Fish and chips",
    "machine": "BBQ Grill",
    "level": 41,
    "price": 244,
    "time_min": 76,
    "xp": 29,
    "profit_per_hour": 21.96078431,
    "xp_per_hour": 22.74509804
  },
  {
    "product": "Lobster skewer",
    "machine": "BBQ Grill",
    "level": 48,
    "price": 417,
    "time_min": 34,
    "xp": 50,
    "profit_per_hour": 45.88235294,
    "xp_per_hour": 88.23529412
  },
  {
    "product": "Garlic bread",
    "machine": "BBQ Grill",
    "level": 60,
    "price": 198,
    "time_min": 12,
    "xp": 24,
    "profit_per_hour": 84.70588235,
    "xp_per_hour": 112.9411765
  },
  {
    "product": "Grilled onion",
    "machine": "BBQ Grill",
    "level": 68,
    "price": 190,
    "time_min": 51,
    "xp": 23,
    "profit_per_hour": 35.29411765,
    "xp_per_hour": 27.05882353
  },
  {
    "product": "Winter veggies",
    "machine": "BBQ Grill",
    "level": 72,
    "price": 198,
    "time_min": 21,
    "xp": 24,
    "profit_per_hour": 36.70588235,
    "xp_per_hour": 67.76470588
  },
  {
    "product": "Stuffed peppers",
    "machine": "BBQ Grill",
    "level": 80,
    "price": 352,
    "time_min": 17,
    "xp": 42,
    "profit_per_hour": 63.52941176,
    "xp_per_hour": 148.2352941
  },
  {
    "product": "Grilled eggplant",
    "machine": "BBQ Grill",
    "level": 90,
    "price": 324,
    "time_min": 34,
    "xp": 39,
    "profit_per_hour": 52.94117647,
    "xp_per_hour": 68.82352941
  },
  {
    "product": "Banana pancakes",
    "machine": "BBQ Grill",
    "level": 94,
    "price": 352,
    "time_min": 51,
    "xp": 42,
    "profit_per_hour": 29.41176471,
    "xp_per_hour": 49.41176471
  },
  {
    "product": "Fish skewer",
    "machine": "BBQ Grill",
    "level": 96,
    "price": 176,
    "time_min": 25,
    "xp": 21,
    "profit_per_hour": 65.88235294,
    "xp_per_hour": 49.41176471
  },
  {
    "product": "Carrot pie",
    "machine": "Pie Oven",
    "level": 14,
    "price": 82,
    "time_min": 51,
    "xp": 10,
    "profit_per_hour": 43.52941176,
    "xp_per_hour": 11.76470588
  },
  {
    "product": "Pumpkin pie",
    "machine": "Pie Oven",
    "level": 15,
    "price": 158,
    "time_min": 102,
    "xp": 19,
    "profit_per_hour": 22.35294118,
    "xp_per_hour": 11.17647059
  },
  {
    "product": "Bacon pie",
    "machine": "Pie Oven",
    "level": 18,
    "price": 219,
    "time_min": 153,
    "xp": 26,
    "profit_per_hour": 17.64705882,
    "xp_per_hour": 10.19607843
  },
  {
    "product": "Apple pie",
    "machine": "Pie Oven",
    "level": 28,
    "price": 270,
    "time_min": 127,
    "xp": 32,
    "profit_per_hour": 18.35294118,
    "xp_per_hour": 15.05882353
  },
  {
    "product": "Fish pie",
    "machine": "Pie Oven",
    "level": 28,
    "price": 226,
    "time_min": 102,
    "xp": 27,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 15.88235294
  },
  {
    "product": "Feta pie",
    "machine": "Pie Oven",
    "level": 34,
    "price": 223,
    "time_min": 76,
    "xp": 26,
    "profit_per_hour": 29.01960784,
    "xp_per_hour": 20.39215686
  },
  {
    "product": "Casserole",
    "machine": "Pie Oven",
    "level": 36,
    "price": 367,
    "time_min": 102,
    "xp": 44,
    "profit_per_hour": 21.76470588,
    "xp_per_hour": 25.88235294
  },
  {
    "product": "Shepherd's pie",
    "machine": "Pie Oven",
    "level": 39,
    "price": 280,
    "time_min": 85,
    "xp": 34,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 24.0
  },
  {
    "product": "Chocolate pie",
    "machine": "Pie Oven",
    "level": 65,
    "price": 514,
    "time_min": 63,
    "xp": 70,
    "profit_per_hour": 76.23529412,
    "xp_per_hour": 65.88235294
  },
  {
    "product": "Lemon pie",
    "machine": "Pie Oven",
    "level": 67,
    "price": 446,
    "time_min": 114,
    "xp": 53,
    "profit_per_hour": 23.00653595,
    "xp_per_hour": 27.7124183
  },
  {
    "product": "Peach tart",
    "machine": "Pie Oven",
    "level": 76,
    "price": 435,
    "time_min": 127,
    "xp": 52,
    "profit_per_hour": 20.23529412,
    "xp_per_hour": 24.47058824
  },
  {
    "product": "Passion fruit pie",
    "machine": "Pie Oven",
    "level": 92,
    "price": 111,
    "time_min": 42,
    "xp": 13,
    "profit_per_hour": 46.58823529,
    "xp_per_hour": 18.35294118
  },
  {
    "product": "Mushroom pot pie",
    "machine": "Pie Oven",
    "level": 97,
    "price": 162,
    "time_min": 51,
    "xp": 19,
    "profit_per_hour": 38.82352941,
    "xp_per_hour": 22.35294118
  },
  {
    "product": "Eggplant parmesan",
    "machine": "Pie Oven",
    "level": 99,
    "price": 442,
    "time_min": 38,
    "xp": 53,
    "profit_per_hour": 75.29411765,
    "xp_per_hour": 83.1372549
  },
  {
    "product": "Sweater",
    "machine": "Loom",
    "level": 17,
    "price": 151,
    "time_min": 102,
    "xp": 18,
    "profit_per_hour": 25.29411765,
    "xp_per_hour": 10.58823529
  },
  {
    "product": "Cotton fabric",
    "machine": "Loom",
    "level": 18,
    "price": 108,
    "time_min": 25,
    "xp": 13,
    "profit_per_hour": 56.47058824,
    "xp_per_hour": 30.58823529
  },
  {
    "product": "Blue woolly hat",
    "machine": "Loom",
    "level": 19,
    "price": 111,
    "time_min": 51,
    "xp": 13,
    "profit_per_hour": 37.64705882,
    "xp_per_hour": 15.29411765
  },
  {
    "product": "Blue sweater",
    "machine": "Loom",
    "level": 20,
    "price": 208,
    "time_min": 153,
    "xp": 25,
    "profit_per_hour": 19.60784314,
    "xp_per_hour": 9.803921569
  },
  {
    "product": "Red scarf",
    "machine": "Loom",
    "level": 48,
    "price": 288,
    "time_min": 127,
    "xp": 34,
    "profit_per_hour": 37.64705882,
    "xp_per_hour": 16.0
  },
  {
    "product": "Flower shawl",
    "machine": "Loom",
    "level": 71,
    "price": 295,
    "time_min": 76,
    "xp": 35,
    "profit_per_hour": 32.94117647,
    "xp_per_hour": 27.45098039
  },
  {
    "product": "Cotton shirt",
    "machine": "Sewing Machine",
    "level": 19,
    "price": 241,
    "time_min": 38,
    "xp": 29,
    "profit_per_hour": 39.21568627,
    "xp_per_hour": 45.49019608
  },
  {
    "product": "Wooly chaps",
    "machine": "Sewing Machine",
    "level": 21,
    "price": 309,
    "time_min": 76,
    "xp": 37,
    "profit_per_hour": 30.58823529,
    "xp_per_hour": 29.01960784
  },
  {
    "product": "Violet dress",
    "machine": "Sewing Machine",
    "level": 25,
    "price": 327,
    "time_min": 114,
    "xp": 39,
    "profit_per_hour": 20.91503268,
    "xp_per_hour": 20.39215686
  },
  {
    "product": "Pillow",
    "machine": "Sewing Machine",
    "level": 51,
    "price": 676,
    "time_min": 153,
    "xp": 81,
    "profit_per_hour": 15.68627451,
    "xp_per_hour": 31.76470588
  },
  {
    "product": "Blanket",
    "machine": "Sewing Machine",
    "level": 59,
    "price": 1098,
    "time_min": 178,
    "xp": 131,
    "profit_per_hour": 14.11764706,
    "xp_per_hour": 44.03361345
  },
  {
    "product": "Carrot cake",
    "machine": "Cake Oven",
    "level": 21,
    "price": 165,
    "time_min": 76,
    "xp": 20,
    "profit_per_hour": 29.01960784,
    "xp_per_hour": 15.68627451
  },
  {
    "product": "Cream cake",
    "machine": "Cake Oven",
    "level": 23,
    "price": 219,
    "time_min": 153,
    "xp": 26,
    "profit_per_hour": 40.78431373,
    "xp_per_hour": 10.19607843
  },
  {
    "product": "Red berry cake",
    "machine": "Cake Oven",
    "level": 23,
    "price": 255,
    "time_min": 51,
    "xp": 31,
    "profit_per_hour": 27.05882353,
    "xp_per_hour": 36.47058824
  },
  {
    "product": "Cheesecake",
    "machine": "Cake Oven",
    "level": 24,
    "price": 284,
    "time_min": 204,
    "xp": 34,
    "profit_per_hour": 17.05882353,
    "xp_per_hour": 10.0
  },
  {
    "product": "Strawberry cake",
    "machine": "Cake Oven",
    "level": 35,
    "price": 316,
    "time_min": 153,
    "xp": 38,
    "profit_per_hour": 41.96078431,
    "xp_per_hour": 14.90196078
  },
  {
    "product": "Chocolate cake",
    "machine": "Cake Oven",
    "level": 36,
    "price": 320,
    "time_min": 102,
    "xp": 38,
    "profit_per_hour": 20.0,
    "xp_per_hour": 22.35294118
  },
  {
    "product": "Potato feta cake",
    "machine": "Cake Oven",
    "level": 38,
    "price": 309,
    "time_min": 102,
    "xp": 37,
    "profit_per_hour": 22.94117647,
    "xp_per_hour": 21.76470588
  },
  {
    "product": "Honey apple cake",
    "machine": "Cake Oven",
    "level": 42,
    "price": 482,
    "time_min": 170,
    "xp": 57,
    "profit_per_hour": 19.05882353,
    "xp_per_hour": 20.11764706
  },
  {
    "product": "Fancy cake",
    "machine": "Cake Oven",
    "level": 54,
    "price": 450,
    "time_min": 12,
    "xp": 49,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 230.5882353
  },
  {
    "product": "Pineapple cake",
    "machine": "Cake Oven",
    "level": 65,
    "price": 259,
    "time_min": 63,
    "xp": 31,
    "profit_per_hour": 31.05882353,
    "xp_per_hour": 29.17647059
  },
  {
    "product": "Lemon cake",
    "machine": "Cake Oven",
    "level": 68,
    "price": 896,
    "time_min": 127,
    "xp": 107,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 50.35294118
  },
  {
    "product": "Fruit cake",
    "machine": "Cake Oven",
    "level": 89,
    "price": 450,
    "time_min": 153,
    "xp": 54,
    "profit_per_hour": 18.43137255,
    "xp_per_hour": 21.17647059
  },
  {
    "product": "Chocolate roll",
    "machine": "Cake Oven",
    "level": 95,
    "price": 604,
    "time_min": 76,
    "xp": 72,
    "profit_per_hour": 14.90196078,
    "xp_per_hour": 56.47058824
  },
  {
    "product": "Silver bar",
    "machine": "Smelter",
    "level": 24,
    "price": 147,
    "time_min": 408,
    "xp": 14,
    "profit_per_hour": 13.67647059,
    "xp_per_hour": 2.058823529
  },
  {
    "product": "Gold bar",
    "machine": "Smelter",
    "level": 25,
    "price": 180,
    "time_min": 612,
    "xp": 18,
    "profit_per_hour": 11.47058824,
    "xp_per_hour": 1.764705882
  },
  {
    "product": "Platinum bar",
    "machine": "Smelter",
    "level": 25,
    "price": 205,
    "time_min": 816,
    "xp": 21,
    "profit_per_hour": 8.014705882,
    "xp_per_hour": 1.544117647
  },
  {
    "product": "Refined coal",
    "machine": "Smelter",
    "level": 33,
    "price": 108,
    "time_min": 306,
    "xp": 13,
    "profit_per_hour": 15.29411765,
    "xp_per_hour": 2.549019608
  },
  {
    "product": "Iron bar",
    "machine": "Smelter",
    "level": 34,
    "price": 129,
    "time_min": 357,
    "xp": 15,
    "profit_per_hour": 14.62184874,
    "xp_per_hour": 2.521008403
  },
  {
    "product": "Carrot juice",
    "machine": "Juice Press",
    "level": 26,
    "price": 46,
    "time_min": 25,
    "xp": 6,
    "profit_per_hour": 58.82352941,
    "xp_per_hour": 14.11764706
  },
  {
    "product": "Apple juice",
    "machine": "Juice Press",
    "level": 28,
    "price": 129,
    "time_min": 102,
    "xp": 15,
    "profit_per_hour": 30.0,
    "xp_per_hour": 8.823529412
  },
  {
    "product": "Cherry juice",
    "machine": "Juice Press",
    "level": 30,
    "price": 216,
    "time_min": 127,
    "xp": 26,
    "profit_per_hour": 37.64705882,
    "xp_per_hour": 12.23529412
  },
  {
    "product": "Tomato juice",
    "machine": "Juice Press",
    "level": 31,
    "price": 162,
    "time_min": 76,
    "xp": 19,
    "profit_per_hour": 25.88235294,
    "xp_per_hour": 14.90196078
  },
  {
    "product": "Berry juice",
    "machine": "Juice Press",
    "level": 31,
    "price": 205,
    "time_min": 153,
    "xp": 24,
    "profit_per_hour": 30.19607843,
    "xp_per_hour": 9.411764706
  },
  {
    "product": "Pineapple juice",
    "machine": "Juice Press",
    "level": 52,
    "price": 68,
    "time_min": 38,
    "xp": 8,
    "profit_per_hour": 40.78431373,
    "xp_per_hour": 12.54901961
  },
  {
    "product": "Orange juice",
    "machine": "Juice Press",
    "level": 71,
    "price": 234,
    "time_min": 102,
    "xp": 28,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 16.47058824
  },
  {
    "product": "Grape juice",
    "machine": "Juice Press",
    "level": 84,
    "price": 104,
    "time_min": 127,
    "xp": 13,
    "profit_per_hour": 18.82352941,
    "xp_per_hour": 6.117647059
  },
  {
    "product": "Passion fruit juice",
    "machine": "Juice Press",
    "level": 88,
    "price": 64,
    "time_min": 38,
    "xp": 8,
    "profit_per_hour": 43.92156863,
    "xp_per_hour": 12.54901961
  },
  {
    "product": "Watermelon juice",
    "machine": "Juice Press",
    "level": 92,
    "price": 108,
    "time_min": 51,
    "xp": 13,
    "profit_per_hour": 35.29411765,
    "xp_per_hour": 15.29411765
  },
  {
    "product": "Mango juice",
    "machine": "Juice Press",
    "level": 97,
    "price": 230,
    "time_min": 42,
    "xp": 27,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 38.11764706
  },
  {
    "product": "Guava Juice",
    "machine": "Juice Press",
    "level": 104,
    "price": 252,
    "time_min": 55,
    "xp": 30,
    "profit_per_hour": 31.41818182,
    "xp_per_hour": 32.72727273
  },
  {
    "product": "Vanilla ice cream",
    "machine": "Ice Cream Maker",
    "level": 29,
    "price": 172,
    "time_min": 102,
    "xp": 20,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 11.76470588
  },
  {
    "product": "Cherry popsicle",
    "machine": "Ice Cream Maker",
    "level": 33,
    "price": 352,
    "time_min": 153,
    "xp": 42,
    "profit_per_hour": 18.03921569,
    "xp_per_hour": 16.47058824
  },
  {
    "product": "Strawberry ice cream",
    "machine": "Ice Cream Maker",
    "level": 34,
    "price": 331,
    "time_min": 204,
    "xp": 40,
    "profit_per_hour": 14.41176471,
    "xp_per_hour": 11.76470588
  },
  {
    "product": "Chocolate ice cream",
    "machine": "Ice Cream Maker",
    "level": 39,
    "price": 342,
    "time_min": 127,
    "xp": 41,
    "profit_per_hour": 17.88235294,
    "xp_per_hour": 19.29411765
  },
  {
    "product": "Sesame ice cream",
    "machine": "Ice Cream Maker",
    "level": 50,
    "price": 176,
    "time_min": 102,
    "xp": 21,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 12.35294118
  },
  {
    "product": "Peanut butter milkshake",
    "machine": "Ice Cream Maker",
    "level": 68,
    "price": 619,
    "time_min": 85,
    "xp": 86,
    "profit_per_hour": 31.76470588,
    "xp_per_hour": 60.70588235
  },
  {
    "product": "Orange sorbet",
    "machine": "Ice Cream Maker",
    "level": 78,
    "price": 399,
    "time_min": 178,
    "xp": 48,
    "profit_per_hour": 17.14285714,
    "xp_per_hour": 16.13445378
  },
  {
    "product": "Affogato​​​​",
    "machine": "Ice Cream Maker",
    "level": 78,
    "price": 435,
    "time_min": 17,
    "xp": 56,
    "profit_per_hour": 52.94117647,
    "xp_per_hour": 197.6470588
  },
  {
    "product": "Peach ice cream",
    "machine": "Ice Cream Maker",
    "level": 83,
    "price": 450,
    "time_min": 153,
    "xp": 54,
    "profit_per_hour": 18.03921569,
    "xp_per_hour": 21.17647059
  },
  {
    "product": "Mint ice cream",
    "machine": "Ice Cream Maker",
    "level": 85,
    "price": 288,
    "time_min": 114,
    "xp": 34,
    "profit_per_hour": 19.86928105,
    "xp_per_hour": 17.77777778
  },
  {
    "product": "Banana split",
    "machine": "Ice Cream Maker",
    "level": 96,
    "price": 403,
    "time_min": 178,
    "xp": 48,
    "profit_per_hour": 15.12605042,
    "xp_per_hour": 16.13445378
  },
  {
    "product": "Coconut Ice Cream",
    "machine": "Ice Cream Maker",
    "level": 102,
    "price": 320,
    "time_min": 15,
    "xp": 38,
    "profit_per_hour": 56.0,
    "xp_per_hour": 152.0
  },
  {
    "product": "Fruit Sorbet",
    "machine": "Ice Cream Maker",
    "level": 106,
    "price": 518,
    "time_min": 60,
    "xp": 62,
    "profit_per_hour": 139.0,
    "xp_per_hour": 62.0
  },
  {
    "product": "Apple jam",
    "machine": "Jam Maker",
    "level": 35,
    "price": 219,
    "time_min": 306,
    "xp": 26,
    "profit_per_hour": 20.0,
    "xp_per_hour": 5.098039216
  },
  {
    "product": "Raspberry jam",
    "machine": "Jam Maker",
    "level": 36,
    "price": 252,
    "time_min": 357,
    "xp": 30,
    "profit_per_hour": 19.15966387,
    "xp_per_hour": 5.042016807
  },
  {
    "product": "Blackberry jam",
    "machine": "Jam Maker",
    "level": 37,
    "price": 388,
    "time_min": 408,
    "xp": 46,
    "profit_per_hour": 20.88235294,
    "xp_per_hour": 6.764705882
  },
  {
    "product": "Cherry jam",
    "machine": "Jam Maker",
    "level": 38,
    "price": 334,
    "time_min": 357,
    "xp": 40,
    "profit_per_hour": 21.8487395,
    "xp_per_hour": 6.722689076
  },
  {
    "product": "Strawberry jam",
    "machine": "Jam Maker",
    "level": 50,
    "price": 270,
    "time_min": 382,
    "xp": 32,
    "profit_per_hour": 18.82352941,
    "xp_per_hour": 5.019607843
  },
  {
    "product": "Marmalade",
    "machine": "Jam Maker",
    "level": 74,
    "price": 457,
    "time_min": 433,
    "xp": 54,
    "profit_per_hour": 22.97577855,
    "xp_per_hour": 7.474048443
  },
  {
    "product": "Peach jam",
    "machine": "Jam Maker",
    "level": 79,
    "price": 464,
    "time_min": 408,
    "xp": 55,
    "profit_per_hour": 24.11764706,
    "xp_per_hour": 8.088235294
  },
  {
    "product": "Grape jam",
    "machine": "Jam Maker",
    "level": 85,
    "price": 162,
    "time_min": 331,
    "xp": 19,
    "profit_per_hour": 11.94570136,
    "xp_per_hour": 3.438914027
  },
  {
    "product": "Plum jam",
    "machine": "Jam Maker",
    "level": 94,
    "price": 385,
    "time_min": 255,
    "xp": 46,
    "profit_per_hour": 32.70588235,
    "xp_per_hour": 10.82352941
  },
  {
    "product": "Passion fruit jam",
    "machine": "Jam Maker",
    "level": 96,
    "price": 118,
    "time_min": 272,
    "xp": 14,
    "profit_per_hour": 14.11764706,
    "xp_per_hour": 3.088235294
  },
  {
    "product": "Bracelet",
    "machine": "Jewler",
    "level": 38,
    "price": 514,
    "time_min": 102,
    "xp": 61,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 35.88235294
  },
  {
    "product": "Necklace",
    "machine": "Jewler",
    "level": 39,
    "price": 727,
    "time_min": 153,
    "xp": 87,
    "profit_per_hour": 18.82352941,
    "xp_per_hour": 34.11764706
  },
  {
    "product": "Diamond ring",
    "machine": "Jewler",
    "level": 40,
    "price": 824,
    "time_min": 204,
    "xp": 98,
    "profit_per_hour": 15.88235294,
    "xp_per_hour": 28.82352941
  },
  {
    "product": "Iron bracelet",
    "machine": "Jewler",
    "level": 41,
    "price": 658,
    "time_min": 76,
    "xp": 79,
    "profit_per_hour": 29.01960784,
    "xp_per_hour": 61.96078431
  },
  {
    "product": "Flower pendant",
    "machine": "Jewler",
    "level": 98,
    "price": 698,
    "time_min": 51,
    "xp": 83,
    "profit_per_hour": 29.41176471,
    "xp_per_hour": 97.64705882
  },
  {
    "product": "Honey",
    "machine": "Honey Extractor",
    "level": 39,
    "price": 154,
    "time_min": 17,
    "xp": 19,
    "profit_per_hour": 63.52941176,
    "xp_per_hour": 67.05882353
  },
  {
    "product": "Beeswax",
    "machine": "Honey Extractor",
    "level": 48,
    "price": 234,
    "time_min": 38,
    "xp": 28,
    "profit_per_hour": 47.05882353,
    "xp_per_hour": 43.92156863
  },
  {
    "product": "Espresso",
    "machine": "Coffee Kiosk",
    "level": 42,
    "price": 248,
    "time_min": 4,
    "xp": 29,
    "profit_per_hour": 84.70588235,
    "xp_per_hour": 409.4117647
  },
  {
    "product": "Caffè latte",
    "machine": "Coffee Kiosk",
    "level": 43,
    "price": 219,
    "time_min": 8,
    "xp": 26,
    "profit_per_hour": 63.52941176,
    "xp_per_hour": 183.5294118
  },
  {
    "product": "Caffè mocha",
    "machine": "Coffee Kiosk",
    "level": 45,
    "price": 291,
    "time_min": 12,
    "xp": 35,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 164.7058824
  },
  {
    "product": "Raspberry mocha",
    "machine": "Coffee Kiosk",
    "level": 46,
    "price": 259,
    "time_min": 25,
    "xp": 31,
    "profit_per_hour": 30.58823529,
    "xp_per_hour": 72.94117647
  },
  {
    "product": "Hot chocolate",
    "machine": "Coffee Kiosk",
    "level": 47,
    "price": 316,
    "time_min": 21,
    "xp": 38,
    "profit_per_hour": 33.88235294,
    "xp_per_hour": 107.2941176
  },
  {
    "product": "Caramel latte",
    "machine": "Coffee Kiosk",
    "level": 62,
    "price": 345,
    "time_min": 12,
    "xp": 41,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 192.9411765
  },
  {
    "product": "Iced banana latte",
    "machine": "Coffee Kiosk",
    "level": 88,
    "price": 277,
    "time_min": 17,
    "xp": 33,
    "profit_per_hour": 45.88235294,
    "xp_per_hour": 116.4705882
  },
  {
    "product": "Lobster tail",
    "machine": "Lobster Pool",
    "level": 44,
    "price": 201,
    "time_min": 360,
    "xp": 24,
    "profit_per_hour": 33.5,
    "xp_per_hour": 4.0
  },
  {
    "product": "Lobster soup",
    "machine": "Soup Kitchen",
    "level": 46,
    "price": 612,
    "time_min": 127,
    "xp": 73,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 34.35294118
  },
  {
    "product": "Tomato soup",
    "machine": "Soup Kitchen",
    "level": 47,
    "price": 478,
    "time_min": 76,
    "xp": 57,
    "profit_per_hour": 25.09803922,
    "xp_per_hour": 44.70588235
  },
  {
    "product": "Pumpkin soup",
    "machine": "Soup Kitchen",
    "level": 49,
    "price": 392,
    "time_min": 102,
    "xp": 47,
    "profit_per_hour": 27.05882353,
    "xp_per_hour": 27.64705882
  },
  {
    "product": "Fish soup",
    "machine": "Soup Kitchen",
    "level": 53,
    "price": 298,
    "time_min": 153,
    "xp": 35,
    "profit_per_hour": 16.8627451,
    "xp_per_hour": 13.7254902
  },
  {
    "product": "Cabbage soup",
    "machine": "Soup Kitchen",
    "level": 65,
    "price": 270,
    "time_min": 76,
    "xp": 32,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 25.09803922
  },
  {
    "product": "Onion soup",
    "machine": "Soup Kitchen",
    "level": 72,
    "price": 327,
    "time_min": 127,
    "xp": 39,
    "profit_per_hour": 21.64705882,
    "xp_per_hour": 18.35294118
  },
  {
    "product": "Noodle soup",
    "machine": "Soup Kitchen",
    "level": 73,
    "price": 432,
    "time_min": 102,
    "xp": 52,
    "profit_per_hour": 27.05882353,
    "xp_per_hour": 30.58823529
  },
  {
    "product": "Potato soup",
    "machine": "Soup Kitchen",
    "level": 78,
    "price": 255,
    "time_min": 127,
    "xp": 31,
    "profit_per_hour": 17.41176471,
    "xp_per_hour": 14.58823529
  },
  {
    "product": "Bell pepper soup",
    "machine": "Soup Kitchen",
    "level": 81,
    "price": 439,
    "time_min": 51,
    "xp": 52,
    "profit_per_hour": 38.82352941,
    "xp_per_hour": 61.17647059
  },
  {
    "product": "Broccoli soup",
    "machine": "Soup Kitchen",
    "level": 87,
    "price": 237,
    "time_min": 63,
    "xp": 28,
    "profit_per_hour": 25.41176471,
    "xp_per_hour": 26.35294118
  },
  {
    "product": "Mushroom soup",
    "machine": "Soup Kitchen",
    "level": 104,
    "price": 176,
    "time_min": 68,
    "xp": 21,
    "profit_per_hour": 31.76470588,
    "xp_per_hour": 18.52941176
  },
  {
    "product": "Strawberry candle",
    "machine": "Candle Maker",
    "level": 48,
    "price": 370,
    "time_min": 102,
    "xp": 44,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 25.88235294
  },
  {
    "product": "Raspberry candle",
    "machine": "Candle Maker",
    "level": 52,
    "price": 360,
    "time_min": 89,
    "xp": 43,
    "profit_per_hour": 22.85714286,
    "xp_per_hour": 28.90756303
  },
  {
    "product": "Lemon candle",
    "machine": "Candle Maker",
    "level": 72,
    "price": 457,
    "time_min": 114,
    "xp": 55,
    "profit_per_hour": 19.34640523,
    "xp_per_hour": 28.75816993
  },
  {
    "product": "Colorful Candles",
    "machine": "Candle Maker",
    "level": 84,
    "price": 324,
    "time_min": 93,
    "xp": 39,
    "profit_per_hour": 23.74331551,
    "xp_per_hour": 25.02673797
  },
  {
    "product": "Floral candle",
    "machine": "Candle Maker",
    "level": 95,
    "price": 442,
    "time_min": 102,
    "xp": 53,
    "profit_per_hour": 11.17647059,
    "xp_per_hour": 31.17647059
  },
  {
    "product": "Rustic bouquet",
    "machine": "Flower Shop",
    "level": 49,
    "price": 208,
    "time_min": 38,
    "xp": 25,
    "profit_per_hour": 53.33333333,
    "xp_per_hour": 39.21568627
  },
  {
    "product": "Bright bouquet",
    "machine": "Flower Shop",
    "level": 65,
    "price": 338,
    "time_min": 17,
    "xp": 40,
    "profit_per_hour": 458.8235294,
    "xp_per_hour": 141.1764706
  },
  {
    "product": "Gracious bouquet",
    "machine": "Flower Shop",
    "level": 73,
    "price": 500,
    "time_min": 34,
    "xp": 60,
    "profit_per_hour": 469.4117647,
    "xp_per_hour": 105.8823529
  },
  {
    "product": "Candy bouquet",
    "machine": "Flower Shop",
    "level": 90,
    "price": 554,
    "time_min": 17,
    "xp": 66,
    "profit_per_hour": 52.94117647,
    "xp_per_hour": 232.9411765
  },
  {
    "product": "Birthday Bouquet",
    "machine": "Flower Shop",
    "level": 92,
    "price": 349,
    "time_min": 17,
    "xp": 42,
    "profit_per_hour": -74.11764706,
    "xp_per_hour": 148.2352941
  },
  {
    "product": "Soft bouquet",
    "machine": "Flower Shop",
    "level": 93,
    "price": 298,
    "time_min": 25,
    "xp": 36,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 84.70588235
  },
  {
    "product": "Veggie bouquet",
    "machine": "Flower Shop",
    "level": 106,
    "price": 352,
    "time_min": 12,
    "xp": 42,
    "profit_per_hour": 103.5294118,
    "xp_per_hour": 197.6470588
  },
  {
    "product": "Duck feather",
    "machine": "Duck Salon",
    "level": 50,
    "price": 140,
    "time_min": 180,
    "xp": 17,
    "profit_per_hour": 46.66666667,
    "xp_per_hour": 5.666666667
  },
  {
    "product": "Caramel apple",
    "machine": "Candy Machine",
    "level": 51,
    "price": 255,
    "time_min": 102,
    "xp": 31,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 18.23529412
  },
  {
    "product": "Toffee",
    "machine": "Candy Machine",
    "level": 52,
    "price": 176,
    "time_min": 76,
    "xp": 21,
    "profit_per_hour": 32.15686275,
    "xp_per_hour": 16.47058824
  },
  {
    "product": "Chocolate",
    "machine": "Candy Machine",
    "level": 54,
    "price": 460,
    "time_min": 1020,
    "xp": 55,
    "profit_per_hour": 6.0,
    "xp_per_hour": 3.235294118
  },
  {
    "product": "Lollipop",
    "machine": "Candy Machine",
    "level": 57,
    "price": 342,
    "time_min": 612,
    "xp": 41,
    "profit_per_hour": 8.235294118,
    "xp_per_hour": 4.019607843
  },
  {
    "product": "Jelly beans",
    "machine": "Candy Machine",
    "level": 60,
    "price": 684,
    "time_min": 1224,
    "xp": 81,
    "profit_per_hour": -0.2941176471,
    "xp_per_hour": 3.970588235
  },
  {
    "product": "Honey peanuts",
    "machine": "Candy Machine",
    "level": 63,
    "price": 540,
    "time_min": 34,
    "xp": 64,
    "profit_per_hour": 268.2352941,
    "xp_per_hour": 112.9411765
  },
  {
    "product": "Cotton Candy",
    "machine": "Candy Machine",
    "level": 75,
    "price": 226,
    "time_min": 25,
    "xp": 27,
    "profit_per_hour": 61.17647059,
    "xp_per_hour": 63.52941176
  },
  {
    "product": "Sesame brittle",
    "machine": "Candy Machine",
    "level": 78,
    "price": 270,
    "time_min": 51,
    "xp": 32,
    "profit_per_hour": 40.0,
    "xp_per_hour": 37.64705882
  },
  {
    "product": "Soy sauce",
    "machine": "Sauce Maker",
    "level": 54,
    "price": 154,
    "time_min": 153,
    "xp": 19,
    "profit_per_hour": 23.92156863,
    "xp_per_hour": 7.450980392
  },
  {
    "product": "Olive oil",
    "machine": "Sauce Maker",
    "level": 60,
    "price": 277,
    "time_min": 38,
    "xp": 33,
    "profit_per_hour": 48.62745098,
    "xp_per_hour": 51.76470588
  },
  {
    "product": "Mayonnaise",
    "machine": "Sauce Maker",
    "level": 62,
    "price": 367,
    "time_min": 12,
    "xp": 44,
    "profit_per_hour": 84.70588235,
    "xp_per_hour": 207.0588235
  },
  {
    "product": "Lemon curd",
    "machine": "Sauce Maker",
    "level": 66,
    "price": 378,
    "time_min": 21,
    "xp": 45,
    "profit_per_hour": 67.76470588,
    "xp_per_hour": 127.0588235
  },
  {
    "product": "Olive dip",
    "machine": "Sauce Maker",
    "level": 66,
    "price": 468,
    "time_min": 38,
    "xp": 56,
    "profit_per_hour": 51.76470588,
    "xp_per_hour": 87.84313725
  },
  {
    "product": "Tomato sauce",
    "machine": "Sauce Maker",
    "level": 69,
    "price": 230,
    "time_min": 25,
    "xp": 27,
    "profit_per_hour": 44.70588235,
    "xp_per_hour": 63.52941176
  },
  {
    "product": "Salsa",
    "machine": "Sauce Maker",
    "level": 77,
    "price": 252,
    "time_min": 17,
    "xp": 30,
    "profit_per_hour": 56.47058824,
    "xp_per_hour": 105.8823529
  },
  {
    "product": "Hummus",
    "machine": "Sauce Maker",
    "level": 95,
    "price": 277,
    "time_min": 25,
    "xp": 33,
    "profit_per_hour": 54.11764706,
    "xp_per_hour": 77.64705882
  },
  {
    "product": "Tart dressing",
    "machine": "Sauce Maker",
    "level": 100,
    "price": 288,
    "time_min": 25,
    "xp": 34,
    "profit_per_hour": 61.17647059,
    "xp_per_hour": 80.0
  },
  {
    "product": "Sushi roll",
    "machine": "Sushi Bar",
    "level": 56,
    "price": 489,
    "time_min": 51,
    "xp": 58,
    "profit_per_hour": 12.94117647,
    "xp_per_hour": 68.23529412
  },
  {
    "product": "Lobster sushi",
    "machine": "Sushi Bar",
    "level": 59,
    "price": 637,
    "time_min": 51,
    "xp": 76,
    "profit_per_hour": 14.11764706,
    "xp_per_hour": 89.41176471
  },
  {
    "product": "Egg sushi",
    "machine": "Sushi Bar",
    "level": 63,
    "price": 550,
    "time_min": 102,
    "xp": 66,
    "profit_per_hour": 12.94117647,
    "xp_per_hour": 38.82352941
  },
  {
    "product": "Big sushi roll",
    "machine": "Sushi Bar",
    "level": 76,
    "price": 648,
    "time_min": 76,
    "xp": 77,
    "profit_per_hour": 15.68627451,
    "xp_per_hour": 60.39215686
  },
  {
    "product": "Rice ball",
    "machine": "Sushi Bar",
    "level": 110,
    "price": 464,
    "time_min": 38,
    "xp": 55,
    "profit_per_hour": 6.274509804,
    "xp_per_hour": 86.2745098
  },
  {
    "product": "Feta salad",
    "machine": "Salad Bar",
    "level": 58,
    "price": 745,
    "time_min": 76,
    "xp": 89,
    "profit_per_hour": 33.7254902,
    "xp_per_hour": 69.80392157
  },
  {
    "product": "BLT salad",
    "machine": "Salad Bar",
    "level": 62,
    "price": 723,
    "time_min": 89,
    "xp": 86,
    "profit_per_hour": 28.23529412,
    "xp_per_hour": 57.81512605
  },
  {
    "product": "Seafood salad",
    "machine": "Salad Bar",
    "level": 64,
    "price": 763,
    "time_min": 102,
    "xp": 91,
    "profit_per_hour": 26.47058824,
    "xp_per_hour": 53.52941176
  },
  {
    "product": "Pasta salad",
    "machine": "Salad Bar",
    "level": 67,
    "price": 759,
    "time_min": 127,
    "xp": 90,
    "profit_per_hour": 17.88235294,
    "xp_per_hour": 42.35294118
  },
  {
    "product": "Veggie platter",
    "machine": "Salad Bar",
    "level": 74,
    "price": 266,
    "time_min": 102,
    "xp": 32,
    "profit_per_hour": 25.88235294,
    "xp_per_hour": 18.82352941
  },
  {
    "product": "Coleslaw",
    "machine": "Salad Bar",
    "level": 75,
    "price": 468,
    "time_min": 63,
    "xp": 56,
    "profit_per_hour": 31.05882353,
    "xp_per_hour": 52.70588235
  },
  {
    "product": "Beetroot salad",
    "machine": "Salad Bar",
    "level": 76,
    "price": 234,
    "time_min": 38,
    "xp": 28,
    "profit_per_hour": 47.05882353,
    "xp_per_hour": 43.92156863
  },
  {
    "product": "Summer rolls",
    "machine": "Salad Bar",
    "level": 78,
    "price": 316,
    "time_min": 51,
    "xp": 38,
    "profit_per_hour": 40.0,
    "xp_per_hour": 44.70588235
  },
  {
    "product": "Fruit salad",
    "machine": "Salad Bar",
    "level": 82,
    "price": 597,
    "time_min": 102,
    "xp": 71,
    "profit_per_hour": 18.82352941,
    "xp_per_hour": 41.76470588
  },
  {
    "product": "Summer salad",
    "machine": "Salad Bar",
    "level": 84,
    "price": 554,
    "time_min": 153,
    "xp": 66,
    "profit_per_hour": 18.03921569,
    "xp_per_hour": 25.88235294
  },
  {
    "product": "Mushroom salad",
    "machine": "Salad Bar",
    "level": 89,
    "price": 216,
    "time_min": 51,
    "xp": 26,
    "profit_per_hour": 37.64705882,
    "xp_per_hour": 30.58823529
  },
  {
    "product": "Veggie bagel",
    "machine": "Sandwich Bar",
    "level": 61,
    "price": 532,
    "time_min": 34,
    "xp": 63,
    "profit_per_hour": 54.70588235,
    "xp_per_hour": 111.1764706
  },
  {
    "product": "Bacon toast",
    "machine": "Sandwich Bar",
    "level": 65,
    "price": 648,
    "time_min": 85,
    "xp": 77,
    "profit_per_hour": 30.35294118,
    "xp_per_hour": 54.35294118
  },
  {
    "product": "Egg sandwich",
    "machine": "Sandwich Bar",
    "level": 66,
    "price": 583,
    "time_min": 68,
    "xp": 69,
    "profit_per_hour": 37.05882353,
    "xp_per_hour": 60.88235294
  },
  {
    "product": "Honey toast",
    "machine": "Sandwich Bar",
    "level": 69,
    "price": 255,
    "time_min": 51,
    "xp": 31,
    "profit_per_hour": 35.29411765,
    "xp_per_hour": 36.47058824
  },
  {
    "product": "Peanut butter and jelly sandwich",
    "machine": "Sandwich Bar",
    "level": 71,
    "price": 673,
    "time_min": 21,
    "xp": 80,
    "profit_per_hour": 409.4117647,
    "xp_per_hour": 225.8823529
  },
  {
    "product": "Cucumber sandwich",
    "machine": "Sandwich Bar",
    "level": 79,
    "price": 464,
    "time_min": 29,
    "xp": 55,
    "profit_per_hour": 54.45378151,
    "xp_per_hour": 110.9243697
  },
  {
    "product": "Onion melt",
    "machine": "Sandwich Bar",
    "level": 84,
    "price": 471,
    "time_min": 76,
    "xp": 50,
    "profit_per_hour": 69.01960784,
    "xp_per_hour": 39.21568627
  },
  {
    "product": "Goat cheese toast",
    "machine": "Sandwich Bar",
    "level": 92,
    "price": 302,
    "time_min": 42,
    "xp": 36,
    "profit_per_hour": 32.47058824,
    "xp_per_hour": 50.82352941
  },
  {
    "product": "Hummus wrap",
    "machine": "Sandwich Bar",
    "level": 109,
    "price": 374,
    "time_min": 25,
    "xp": 45,
    "profit_per_hour": 54.11764706,
    "xp_per_hour": 105.8823529
  },
  {
    "product": "Berry smoothie",
    "machine": "Smoothie Mixer",
    "level": 64,
    "price": 547,
    "time_min": 63,
    "xp": 65,
    "profit_per_hour": 12.23529412,
    "xp_per_hour": 61.17647059
  },
  {
    "product": "Green smoothie",
    "machine": "Smoothie Mixer",
    "level": 66,
    "price": 320,
    "time_min": 38,
    "xp": 38,
    "profit_per_hour": 43.92156863,
    "xp_per_hour": 59.60784314
  },
  {
    "product": "Yogurt smoothie",
    "machine": "Smoothie Mixer",
    "level": 70,
    "price": 349,
    "time_min": 51,
    "xp": 42,
    "profit_per_hour": 104.7058824,
    "xp_per_hour": 49.41176471
  },
  {
    "product": "Cucumber smoothie",
    "machine": "Smoothie Mixer",
    "level": 70,
    "price": 266,
    "time_min": 34,
    "xp": 32,
    "profit_per_hour": 49.41176471,
    "xp_per_hour": 56.47058824
  },
  {
    "product": "Mixed smoothie",
    "machine": "Smoothie Mixer",
    "level": 88,
    "price": 504,
    "time_min": 25,
    "xp": 60,
    "profit_per_hour": 40.0,
    "xp_per_hour": 141.1764706
  },
  {
    "product": "Black sesame smoothie",
    "machine": "Smoothie Mixer",
    "level": 93,
    "price": 313,
    "time_min": 38,
    "xp": 37,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 58.03921569
  },
  {
    "product": "Cocoa smoothie",
    "machine": "Smoothie Mixer",
    "level": 100,
    "price": 511,
    "time_min": 34,
    "xp": 61,
    "profit_per_hour": 22.94117647,
    "xp_per_hour": 107.6470588
  },
  {
    "product": "Plum smoothie",
    "machine": "Smoothie Mixer",
    "level": 102,
    "price": 522,
    "time_min": 29,
    "xp": 62,
    "profit_per_hour": 116.9747899,
    "xp_per_hour": 125.0420168
  },
  {
    "product": "Tropical Smoothie",
    "machine": "Smoothie Mixer",
    "level": 104,
    "price": 475,
    "time_min": 40,
    "xp": 57,
    "profit_per_hour": 40.5,
    "xp_per_hour": 85.5
  },
  {
    "product": "Fresh pasta",
    "machine": "Pasta Maker",
    "level": 67,
    "price": 43,
    "time_min": 12,
    "xp": 5,
    "profit_per_hour": 89.41176471,
    "xp_per_hour": 23.52941176
  },
  {
    "product": "Rice noodles",
    "machine": "Pasta Maker",
    "level": 73,
    "price": 100,
    "time_min": 17,
    "xp": 12,
    "profit_per_hour": 35.29411765,
    "xp_per_hour": 42.35294118
  },
  {
    "product": "Fried rice",
    "machine": "Wok Kitchen",
    "level": 69,
    "price": 205,
    "time_min": 51,
    "xp": 24,
    "profit_per_hour": 29.41176471,
    "xp_per_hour": 28.23529412
  },
  {
    "product": "Spicy fish",
    "machine": "Wok Kitchen",
    "level": 79,
    "price": 543,
    "time_min": 76,
    "xp": 65,
    "profit_per_hour": 26.66666667,
    "xp_per_hour": 50.98039216
  },
  {
    "product": "Peanut noodles",
    "machine": "Wok Kitchen",
    "level": 86,
    "price": 669,
    "time_min": 38,
    "xp": 80,
    "profit_per_hour": 240.0,
    "xp_per_hour": 125.4901961
  },
  {
    "product": "Tofu stir fry",
    "machine": "Wok Kitchen",
    "level": 89,
    "price": 306,
    "time_min": 63,
    "xp": 37,
    "profit_per_hour": 39.52941176,
    "xp_per_hour": 34.82352941
  },
  {
    "product": "Cloche hat",
    "machine": "Hat Maker",
    "level": 70,
    "price": 468,
    "time_min": 102,
    "xp": 56,
    "profit_per_hour": 25.88235294,
    "xp_per_hour": 32.94117647
  },
  {
    "product": "Top hat",
    "machine": "Hat Maker",
    "level": 72,
    "price": 619,
    "time_min": 178,
    "xp": 74,
    "profit_per_hour": 15.79831933,
    "xp_per_hour": 24.87394958
  },
  {
    "product": "Sun hat",
    "machine": "Hat Maker",
    "level": 74,
    "price": 558,
    "time_min": 127,
    "xp": 66,
    "profit_per_hour": 21.17647059,
    "xp_per_hour": 31.05882353
  },
  {
    "product": "Flower crown",
    "machine": "Hat Maker",
    "level": 86,
    "price": 331,
    "time_min": 102,
    "xp": 40,
    "profit_per_hour": 22.94117647,
    "xp_per_hour": 23.52941176
  },
  {
    "product": "Gnocchi",
    "machine": "Pasta Kitchen",
    "level": 72,
    "price": 475,
    "time_min": 68,
    "xp": 57,
    "profit_per_hour": 28.23529412,
    "xp_per_hour": 50.29411765
  },
  {
    "product": "Veggie lasagna",
    "machine": "Pasta Kitchen",
    "level": 74,
    "price": 532,
    "time_min": 85,
    "xp": 63,
    "profit_per_hour": 31.05882353,
    "xp_per_hour": 44.47058824
  },
  {
    "product": "Lobster pasta",
    "machine": "Pasta Kitchen",
    "level": 79,
    "price": 637,
    "time_min": 102,
    "xp": 76,
    "profit_per_hour": 20.58823529,
    "xp_per_hour": 44.70588235
  },
  {
    "product": "Pasta carbonara",
    "machine": "Pasta Kitchen",
    "level": 83,
    "price": 410,
    "time_min": 127,
    "xp": 49,
    "profit_per_hour": 19.29411765,
    "xp_per_hour": 23.05882353
  },
  {
    "product": "Broccoli pasta",
    "machine": "Pasta Kitchen",
    "level": 83,
    "price": 345,
    "time_min": 51,
    "xp": 41,
    "profit_per_hour": 36.47058824,
    "xp_per_hour": 48.23529412
  },
  {
    "product": "Spicy pasta",
    "machine": "Pasta Kitchen",
    "level": 87,
    "price": 576,
    "time_min": 76,
    "xp": 69,
    "profit_per_hour": 24.31372549,
    "xp_per_hour": 54.11764706
  },
  {
    "product": "Mushroom pasta",
    "machine": "Pasta Kitchen",
    "level": 101,
    "price": 280,
    "time_min": 63,
    "xp": 33,
    "profit_per_hour": 34.82352941,
    "xp_per_hour": 31.05882353
  },
  {
    "product": "Hot dog",
    "machine": "Hot Dog Stand",
    "level": 75,
    "price": 370,
    "time_min": 25,
    "xp": 44,
    "profit_per_hour": 44.70588235,
    "xp_per_hour": 103.5294118
  },
  {
    "product": "Tofu dog",
    "machine": "Hot Dog Stand",
    "level": 76,
    "price": 367,
    "time_min": 38,
    "xp": 44,
    "profit_per_hour": 61.17647059,
    "xp_per_hour": 69.01960784
  },
  {
    "product": "Corn dog",
    "machine": "Hot Dog Stand",
    "level": 78,
    "price": 529,
    "time_min": 51,
    "xp": 63,
    "profit_per_hour": 28.23529412,
    "xp_per_hour": 74.11764706
  },
  {
    "product": "Onion dog",
    "machine": "Hot Dog Stand",
    "level": 80,
    "price": 306,
    "time_min": 63,
    "xp": 36,
    "profit_per_hour": 30.11764706,
    "xp_per_hour": 33.88235294
  },
  {
    "product": "Plain Donut",
    "machine": "Donut maker",
    "level": 76,
    "price": 129,
    "time_min": 12,
    "xp": 15,
    "profit_per_hour": 94.11764706,
    "xp_per_hour": 70.58823529
  },
  {
    "product": "Sprinkled Donut",
    "machine": "Donut maker",
    "level": 79,
    "price": 313,
    "time_min": 17,
    "xp": 37,
    "profit_per_hour": 42.35294118,
    "xp_per_hour": 130.5882353
  },
  {
    "product": "Crunchy Donut",
    "machine": "Donut maker",
    "level": 82,
    "price": 594,
    "time_min": 25,
    "xp": 71,
    "profit_per_hour": 341.1764706,
    "xp_per_hour": 167.0588235
  },
  {
    "product": "Cream Donut",
    "machine": "Donut maker",
    "level": 86,
    "price": 230,
    "time_min": 21,
    "xp": 27,
    "profit_per_hour": 53.64705882,
    "xp_per_hour": 76.23529412
  },
  {
    "product": "Bacon Donut",
    "machine": "Donut maker",
    "level": 88,
    "price": 388,
    "time_min": 25,
    "xp": 46,
    "profit_per_hour": 44.70588235,
    "xp_per_hour": 108.2352941
  },
  {
    "product": "Filled Donut",
    "machine": "Donut maker",
    "level": 93,
    "price": 403,
    "time_min": 29,
    "xp": 48,
    "profit_per_hour": 44.3697479,
    "xp_per_hour": 96.80672269
  },
  {
    "product": "Taco",
    "machine": "Taco Kitchen",
    "level": 77,
    "price": 396,
    "time_min": 38,
    "xp": 47,
    "profit_per_hour": 34.50980392,
    "xp_per_hour": 73.7254902
  },
  {
    "product": "Fish taco",
    "machine": "Taco Kitchen",
    "level": 79,
    "price": 392,
    "time_min": 76,
    "xp": 47,
    "profit_per_hour": 22.74509804,
    "xp_per_hour": 36.8627451
  },
  {
    "product": "Quesadilla",
    "machine": "Taco Kitchen",
    "level": 82,
    "price": 241,
    "time_min": 51,
    "xp": 29,
    "profit_per_hour": 41.17647059,
    "xp_per_hour": 34.11764706
  },
  {
    "product": "Nachos",
    "machine": "Taco Kitchen",
    "level": 87,
    "price": 432,
    "time_min": 63,
    "xp": 52,
    "profit_per_hour": 28.23529412,
    "xp_per_hour": 48.94117647
  },
  {
    "product": "Green tea",
    "machine": "Tea Stand",
    "level": 80,
    "price": 241,
    "time_min": 25,
    "xp": 29,
    "profit_per_hour": 61.17647059,
    "xp_per_hour": 68.23529412
  },
  {
    "product": "Milk tea",
    "machine": "Tea Stand",
    "level": 81,
    "price": 190,
    "time_min": 38,
    "xp": 23,
    "profit_per_hour": 45.49019608,
    "xp_per_hour": 36.07843137
  },
  {
    "product": "Honey tea",
    "machine": "Tea Stand",
    "level": 83,
    "price": 313,
    "time_min": 34,
    "xp": 37,
    "profit_per_hour": 52.94117647,
    "xp_per_hour": 65.29411765
  },
  {
    "product": "Lemon tea",
    "machine": "Tea Stand",
    "level": 86,
    "price": 241,
    "time_min": 17,
    "xp": 29,
    "profit_per_hour": 67.05882353,
    "xp_per_hour": 102.3529412
  },
  {
    "product": "Apple ginger tea",
    "machine": "Tea Stand",
    "level": 88,
    "price": 169,
    "time_min": 25,
    "xp": 20,
    "profit_per_hour": 47.05882353,
    "xp_per_hour": 47.05882353
  },
  {
    "product": "Orange tea",
    "machine": "Tea Stand",
    "level": 89,
    "price": 255,
    "time_min": 34,
    "xp": 30,
    "profit_per_hour": 51.17647059,
    "xp_per_hour": 52.94117647
  },
  {
    "product": "Iced tea",
    "machine": "Tea Stand",
    "level": 92,
    "price": 252,
    "time_min": 25,
    "xp": 30,
    "profit_per_hour": 54.11764706,
    "xp_per_hour": 70.58823529
  },
  {
    "product": "Mint tea",
    "machine": "Tea Stand",
    "level": 97,
    "price": 255,
    "time_min": 29,
    "xp": 31,
    "profit_per_hour": 110.9243697,
    "xp_per_hour": 62.5210084
  },
  {
    "product": "Chocolate fondue",
    "machine": "Fondue Pot",
    "level": 81,
    "price": 626,
    "time_min": 21,
    "xp": 74,
    "profit_per_hour": 45.17647059,
    "xp_per_hour": 208.9411765
  },
  {
    "product": "Bacon fondue",
    "machine": "Fondue Pot",
    "level": 86,
    "price": 507,
    "time_min": 25,
    "xp": 60,
    "profit_per_hour": 54.11764706,
    "xp_per_hour": 141.1764706
  },
  {
    "product": "Cheese fondue",
    "machine": "Fondue Pot",
    "level": 91,
    "price": 493,
    "time_min": 17,
    "xp": 59,
    "profit_per_hour": 84.70588235,
    "xp_per_hour": 208.2352941
  },
  {
    "product": "Tropical fondue",
    "machine": "Fondue Pot",
    "level": 100,
    "price": 417,
    "time_min": 29,
    "xp": 50,
    "profit_per_hour": 50.42016807,
    "xp_per_hour": 100.8403361
  },
  {
    "product": "Honey soap",
    "machine": "Bath Kiosk",
    "level": 84,
    "price": 327,
    "time_min": 51,
    "xp": 39,
    "profit_per_hour": 27.05882353,
    "xp_per_hour": 45.88235294
  },
  {
    "product": "Lemon lotion",
    "machine": "Bath Kiosk",
    "level": 84,
    "price": 403,
    "time_min": 63,
    "xp": 48,
    "profit_per_hour": 31.05882353,
    "xp_per_hour": 45.17647059
  },
  {
    "product": "Exfoliating soap",
    "machine": "Bath Kiosk",
    "level": 93,
    "price": 363,
    "time_min": 51,
    "xp": 43,
    "profit_per_hour": 20.0,
    "xp_per_hour": 50.58823529
  },
  {
    "product": "Honey face mask",
    "machine": "Bath Kiosk",
    "level": 99,
    "price": 320,
    "time_min": 76,
    "xp": 38,
    "profit_per_hour": 29.01960784,
    "xp_per_hour": 29.80392157
  },
  {
    "product": "Bacon fries",
    "machine": "Deep Fryer",
    "level": 87,
    "price": 302,
    "time_min": 21,
    "xp": 36,
    "profit_per_hour": 22.58823529,
    "xp_per_hour": 101.6470588
  },
  {
    "product": "Hand pies",
    "machine": "Deep Fryer",
    "level": 91,
    "price": 295,
    "time_min": 17,
    "xp": 35,
    "profit_per_hour": 88.23529412,
    "xp_per_hour": 123.5294118
  },
  {
    "product": "Chili poppers",
    "machine": "Deep Fryer",
    "level": 98,
    "price": 406,
    "time_min": 34,
    "xp": 48,
    "profit_per_hour": 40.58823529,
    "xp_per_hour": 84.70588235
  },
  {
    "product": "Falafel",
    "machine": "Deep Fryer",
    "level": 98,
    "price": 226,
    "time_min": 46,
    "xp": 27,
    "profit_per_hour": 38.5026738,
    "xp_per_hour": 34.65240642
  },
  {
    "product": "Fried candy bar",
    "machine": "Deep Fryer",
    "level": 100,
    "price": 658,
    "time_min": 12,
    "xp": 87,
    "profit_per_hour": 291.7647059,
    "xp_per_hour": 409.4117647
  },
  {
    "product": "Samosa",
    "machine": "Deep Fryer",
    "level": 103,
    "price": 223,
    "time_min": 63,
    "xp": 27,
    "profit_per_hour": 29.17647059,
    "xp_per_hour": 25.41176471
  },
  {
    "product": "Pickles",
    "machine": "Preservation station",
    "level": 91,
    "price": 270,
    "time_min": 204,
    "xp": 32,
    "profit_per_hour": 16.76470588,
    "xp_per_hour": 9.411764706
  },
  {
    "product": "Canned fish",
    "machine": "Preservation station",
    "level": 95,
    "price": 471,
    "time_min": 187,
    "xp": 56,
    "profit_per_hour": 16.04278075,
    "xp_per_hour": 17.96791444
  },
  {
    "product": "Kimchi",
    "machine": "Preservation station",
    "level": 98,
    "price": 219,
    "time_min": 255,
    "xp": 26,
    "profit_per_hour": 12.0,
    "xp_per_hour": 6.117647059
  },
  {
    "product": "Dried fruit",
    "machine": "Preservation station",
    "level": 102,
    "price": 266,
    "time_min": 153,
    "xp": 32,
    "profit_per_hour": 16.07843137,
    "xp_per_hour": 12.54901961
  },
  {
    "product": "Guava Compote",
    "machine": "Preservation station",
    "level": 104,
    "price": 421,
    "time_min": 260,
    "xp": 50,
    "profit_per_hour": 12.92307692,
    "xp_per_hour": 11.53846154
  },
  {
    "product": "Tea pot",
    "machine": "Pottery Studio",
    "level": 94,
    "price": 219,
    "time_min": 187,
    "xp": 26,
    "profit_per_hour": 25.6684492,
    "xp_per_hour": 8.342245989
  },
  {
    "product": "Potted plant",
    "machine": "Pottery Studio",
    "level": 96,
    "price": 151,
    "time_min": 187,
    "xp": 26,
    "profit_per_hour": 24.38502674,
    "xp_per_hour": 8.342245989
  },
  {
    "product": "Clay mug",
    "machine": "Pottery Studio",
    "level": 99,
    "price": 212,
    "time_min": 170,
    "xp": 25,
    "profit_per_hour": 25.41176471,
    "xp_per_hour": 8.823529412
  },
  {
    "product": "Rich fudge",
    "machine": "Fudge Shop",
    "level": 99,
    "price": 644,
    "time_min": 102,
    "xp": 77,
    "profit_per_hour": 23.52941176,
    "xp_per_hour": 45.29411765
  },
  {
    "product": "Mint fudge",
    "machine": "Fudge Shop",
    "level": 102,
    "price": 522,
    "time_min": 127,
    "xp": 62,
    "profit_per_hour": 18.82352941,
    "xp_per_hour": 29.17647059
  },
  {
    "product": "Chili fudge",
    "machine": "Fudge Shop",
    "level": 104,
    "price": 540,
    "time_min": 144,
    "xp": 64,
    "profit_per_hour": 19.10034602,
    "xp_per_hour": 26.57439446
  },
  {
    "product": "Lemon fudge",
    "machine": "Fudge Shop",
    "level": 108,
    "price": 590,
    "time_min": 93,
    "xp": 70,
    "profit_per_hour": 28.23529412,
    "xp_per_hour": 44.9197861
  },
  {
    "product": "Peanut fudge",
    "machine": "Fudge Shop",
    "level": 111,
    "price": 1141,
    "time_min": 76,
    "xp": 136,
    "profit_per_hour": 41.56862745,
    "xp_per_hour": 106.6666667
  },
  {
    "product": "Plain Yogurt",
    "machine": "Yogurt Maker",
    "level": 103,
    "price": 234,
    "time_min": 102,
    "xp": 28,
    "profit_per_hour": 22.35294118,
    "xp_per_hour": 16.47058824
  },
  {
    "product": "Strawberry Yogurt",
    "machine": "Yogurt Maker",
    "level": 105,
    "price": 529,
    "time_min": 34,
    "xp": 63,
    "profit_per_hour": 44.11764706,
    "xp_per_hour": 111.1764706
  },
  {
    "product": "Tropical Yogurt",
    "machine": "Yogurt Maker",
    "level": 109,
    "price": 457,
    "time_min": 51,
    "xp": 54,
    "profit_per_hour": -210.5882353,
    "xp_per_hour": 63.52941176
  },
  {
    "product": "Chickpea Stew",
    "machine": "Stew Pot",
    "level": 106,
    "price": 284,
    "time_min": 90,
    "xp": 34,
    "profit_per_hour": 24.0,
    "xp_per_hour": 22.66666667
  },
  {
    "product": "Chili Stew",
    "machine": "Stew Pot",
    "level": 109,
    "price": 370,
    "time_min": 120,
    "xp": 44,
    "profit_per_hour": 17.0,
    "xp_per_hour": 22.0
  },
  {
    "product": "Winter Stew",
    "machine": "Stew Pot",
    "level": 112,
    "price": 295,
    "time_min": 240,
    "xp": 35,
    "profit_per_hour": 9.75,
    "xp_per_hour": 8.75
  },
  {
    "product": "Plain Cupcake",
    "machine": "Cupcake Maker",
    "level": 109,
    "price": 280,
    "time_min": 40,
    "xp": 34,
    "profit_per_hour": 43.5,
    "xp_per_hour": 51.0
  },
  {
    "product": "Guava Cupcake",
    "machine": "Cupcake Maker",
    "level": 109,
    "price": 583,
    "time_min": 70,
    "xp": 70,
    "profit_per_hour": 26.57142857,
    "xp_per_hour": 60.0
  },
  {
    "product": "Tropical Cupcake",
    "machine": "Cupcake Maker",
    "level": 112,
    "price": 572,
    "time_min": 90,
    "xp": 68,
    "profit_per_hour": 22.66666667,
    "xp_per_hour": 45.33333333
  },
  {
    "product": "Cookie Cupcake",
    "machine": "Cupcake Maker",
    "level": 114,
    "price": 712,
    "time_min": 120,
    "xp": 85,
    "profit_per_hour": 69.0,
    "xp_per_hour": 42.5
  }
];