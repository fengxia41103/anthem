# anthem

Demo project using given private data set for data visualization. Data
is in CSV format saved in `dist/downloads` folder. CSV is parsed on the fly
and column mapping is hardcoded.

## Dev

1. Git clone this repo
2. `npm install`, will pull down all requested packages
3. `npm run dev`
4. browser go to `http://localhost:8080`

Tested in Node v5.0.0. Recommend to use with NVM for compatibility test.

## Production

1. `npm build`
2. push files in `/dist` to server

## Todo

1. Replace CSV file with a URL so data can be pulled down from remote host

