// main.js
require('es5-shim');
require('es5-shim/es5-sham');
require('console-polyfill');
require("materialize-loader");
require("font-awesome/css/font-awesome.css");
require("./stylesheets/my.css");

import React from "react";
import ReactDom from "react-dom";
import Header from "./header.jsx";
import Footer from "./footer.jsx";
import ChenBox from "./chenmin.jsx";

var Page = React.createClass({
  render () {
    return (
      <div id="wrap" style={{backgroundColor: "#fefefe"}}>
        <Header />
        <ChenBox />
        <Footer />
      </div>
    );
  }
});

ReactDom.render(<Page />, document.getElementById("app"));
