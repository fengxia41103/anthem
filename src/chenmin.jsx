import React from 'react';
import GraphFactory from "./graph.jsx";

var _ = require("lodash");
var classNames = require('classnames');

var randomId = function(){
    return "MY"+(Math.random()*1e32).toString(12);
};

var ChenBox = React.createClass({
    getInitialState: function(){
        return {
            data: [],
            keys: [],
            selectedKeys: ["100", "1000", "1100"]
        }
    },
    handleClick: function(key){
        var tmp = this.state.selectedKeys.slice();
        if (_.includes(tmp,key)){
           // deselect
           _.remove(tmp, function(n){
               return n === key;
           });
        }else{
           tmp.push(key);
        }

        this.setState({
            selectedKeys: tmp
        });
    },
    _cleanData: function(data){
        var tmp = data.map(function(l){
            var volume = parseInt(l[9]);
            var t = Math.floor(parseInt(l[4])/100000);
            t = Math.floor(t/5)*5;

            return {
                volume: volume,
                interval: t
            }
        });

        var tt = _.groupBy(tmp, function(item){
            return item.volume
        });
        for (var k in tt){
        	if (typeof k != "undefined" || k){
            	tt[k] = _.countBy(tt[k], function(item){
                	return item.interval;
            	});
            }
        }

        this.setState({
            data: tt,
            keys: Object.keys(tt)
        });
    },
    componentWillMount: function(){
        var cleanData = this._cleanData;
        var that = this;
        Papa.parse("/downloads/000721.csv", {
            download: true,
            complete: function(results) {
                results.data.shift(); // remove title line
                cleanData(results.data);
            }
        });
    },
    render: function(){
        var data = this.state.data;
        var selectedKeys = this.state.selectedKeys;
        var selected = [];
        for (var i=0; i<selectedKeys.length; i++){
            var d = data[selectedKeys[i]];
            for (var interval in d){
                selected.push({
                    vol: ""+selectedKeys[i],
                    time: parseInt(interval),
                    count: d[interval]
                });
            }
        }

        return (
        <div>
            <div className="container">
                <ChenIndex handleClick={this.handleClick}
                    allKeys={this.state.keys}
                    selectedKeys={this.state.selectedKeys}
                    data={this.state.data} />

            </div>

            <GraphFactory
                data={selected}
                type="bar"
                title="Chenmin demo"
                countryCode=""
                footer="Chenmin demo"/>
        </div>

        );
    }
});


var ChenIndex = React.createClass({
    getInitialState: function(){
        return {
            index: "1"
        }
    },
    setIndex: function(letter){
        this.setState({
            index: letter
        });
    },
    render: function(){
        // Build A-Z index
        var alphabet = [];
        alphabet = "123456789".split("");

        var current = this.state.index;
        var setIndex = this.setIndex;
        var index = alphabet.map(function(letter){
            var highlight = classNames(
                {"active": current==letter}
            );
            return (
                <li key={letter}
                    className={highlight}
                    onClick={setIndex.bind(null,letter)}>
                       <a>{letter}</a>
                </li>
            );
        });


        // Index
        var handleClick = this.props.handleClick;
        var selectedKeys = this.props.selectedKeys;
        var canShow = _.filter(this.props.allKeys, function(key){
            // How to filter all data list per selected index
            return _.startsWith(key, current);
        });
        var keys = canShow.map(function(key){
            var itemClass = classNames(
                "chip",
                {'teal lighten-2 grey-text text-lighten-4': _.includes(selectedKeys,key)}
            );

            var id = randomId();
            return (
               <div key={id}
                   onClick={handleClick.bind(null,key)}
                   className={itemClass}>
                 {key}
               </div>
            );
        });

        // Render
        return (
        <div>
            <nav className="hide-on-med-and-down">
                <div className="nav-wrapper">
                <ul className="left">
                    {index}
                </ul>
                </div>
            </nav>

            <div>
                <h3>{current}</h3>
                {keys}
                <div className="divider"></div>
            </div>

        </div>
        );
    }
});
module.exports = ChenBox;
