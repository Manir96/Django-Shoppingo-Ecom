$(function() {
	"use strict";

        $( "#slider-range" ).slider({
          range: true,
          min: 0,
          max: 500,
          values: [ 75, 300 ],
          slide: function( event, ui ) {
            $( "#amount" ).val( "$" + ui.values[ 0 ] + " - $" + ui.values[ 1 ] );
          }
        });
        $( "#amount" ).val( "$" + $( "#slider-range" ).slider( "values", 0 ) +
          " - $" + $( "#slider-range" ).slider( "values", 1 ) );
     




// colors 

$(document).ready(function(){

	$('.color-slider--').slick({
	   dots: false,
	   arrows: false,
	   infinite: true,
	   speed: 300,
	   slidesToShow: 1,
	   slidesToScroll: 1,
	   autoplay: true,
	   //centerMode: true,
	   prevArrow: "<button type='button' class='slick-prev pull-left'><i class='bi bi-chevron-left'></i></button>",
	   nextArrow: "<button type='button' class='slick-next pull-right'><i class='bi bi-chevron-right'></i></button>",
	   responsive: [
		 {
		   breakpoint: 1025,
		   settings: {
			 slidesToShow: 1,
			 slidesToScroll: 1,
			 infinite: true,
		   }
		 },
		 {
		   breakpoint: 769,
		   settings: {
			 slidesToShow: 1,
			 slidesToScroll: 1,
			 arrows: false,
		   }
		 },
		 {
		   breakpoint: 500,
		   settings: {
			 slidesToShow: 6,
			 slidesToScroll: 1,
			 arrows: false,
		   }
		 }
	   ]
	 });
	 
  
   });
  






});