

$(function() {
	"use strict";



  $(".mobile-search-button").on("click", function() {

    $(".searchbar").addClass("full-search-bar")

  }),

  $(".search-close-icon").on("click", function() {

    $(".searchbar").removeClass("full-search-bar")

  })



  //Side nav

  $(function () {

      $('#sidenav').metisMenu();

  });

 

  // Acive Menu

  $(function() {
    for (var e = window.location, o = $(".metismenu li a").filter(function() {
        return this.href == e
      }).addClass("").parent().addClass("mm-active"); o.is("li");) o = o.parent("").addClass("mm-show").parent("").addClass("mm-active")
  });



});