const navigate = (to, isReplace = false) => {
    console.log(`navigate: ${to}: ${isReplace}`);
    const historyChangeEvent = new CustomEvent("historychange", {
        detail: {
            to,
            isReplace,
        },
    });

    dispatchEvent(historyChangeEvent);
};

const reload = ($) => {
    "use strict";
    console.log(`reload`);

    $(".render")
        .off("click")
        .on("click", (e) => {
            const target = e.target.closest("a");
            if (!(target instanceof HTMLAnchorElement)) return;

            e.preventDefault();
            const targetURL = e.target.pathname;
            navigate(targetURL);
        });

    // Spinner
    var spinner = () => {
        setTimeout(() => {
            if ($('#spinner').length > 0) {
                $('#spinner').removeClass('show');
            }
        }, 1);
    };
    spinner();
    $('#calender').datetimepicker({
        inline: true,
        format: 'L'
    });
};

$(document).ready(() => {
    $('.back-to-top').click(() => {
        $('html, body').animate({ scrollTop: 0 }, 1500, 'easeInOutExpo');
        return false;
    });


    // Sidebar Toggler
    $('.sidebar-toggler').click(() => {
        $('.sidebar, .content').toggleClass("open");
        return false;
    });


    // Progress Bar
    $('.pg-bar').waypoint(() => {
        $('.progress .progress-bar').each(() => {
            $(this).css("width", $(this).attr("aria-valuenow") + '%');
        });
    }, { offset: '80%' });


    $(window).scroll(() => {
        if ($(this).scrollTop() > 300) {
            $('.back-to-top').fadeIn('slow');
        } else {
            $('.back-to-top').fadeOut('slow');
        }
    }).on("historychange", ({ detail }) => {
        console.log("history change");
        console.log(detail);
        const { to, isReplace } = detail;
        let nowUrl = location.pathname
        if (isReplace || to === nowUrl)
            history.replaceState(true, "", to);
        else history.pushState(false, "", to);

        csr_render(to);

    }).on("popstate", (event) => {
        console.log(`state pop:`);
        console.log(event);
        let previousUrl = location.pathname;
        csr_render(previousUrl);

    })

    reload(jQuery);
});