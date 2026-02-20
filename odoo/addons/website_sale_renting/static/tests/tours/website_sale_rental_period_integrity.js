import { registry } from '@web/core/registry';
import { clickOnElement } from '@website/js/tours/tour_utils';
import * as tourUtils from '@website_sale/js/tours/tour_utils';

function getValidNextDatetime() {
    return luxon.DateTime.now().plus({ weeks: 1 }).set({ weekday: 1 }).toFormat('MM/dd/yyyy');
}

const expectedDate = getValidNextDatetime();

registry.category('web_tour.tours').add('website_sale_rental_period_integrity', {
    url: '/shop',
    steps: () => [
        ...tourUtils.searchProduct("Product A"),
        clickOnElement('Product A', 'a:contains("Product A")'),
        {
            content: "Define end date",
            trigger: 'input[name=renting_end_date]',
            run: `edit ${expectedDate} && press Tab`,
        },
        {
            content: "Define start date",
            trigger: 'input[name=renting_start_date]',
            run: `edit ${expectedDate} && press Tab`,
        },
        clickOnElement('Add to cart', '#add_to_cart'),
        {
            content: "Wait for rental dates to be synchronized",
            trigger: 'input[name="renting_end_date"][disabled]',
        },
        ...tourUtils.searchProduct("Product B"),
        clickOnElement('Product B', 'a:contains("Product B")'),
        {
            content: "Verify disabled rental start date",
            trigger: 'input[name="renting_start_date"][disabled]',
        },
        {
            content: "Verify disabled rental end date",
            trigger: 'input[name="renting_end_date"][disabled]',
        },
        {
            content: "Verify synchronized rental dates",
            trigger: 'body',
            run: () => {
                const startDate = document.querySelector('input[name="renting_start_date"]').value;
                const endDate = document.querySelector('input[name="renting_end_date"]').value;

                if (startDate !== endDate || startDate !== expectedDate) {
                    throw new Error(`Rental dates should both match ${expectedDate}`);
                }
            }
        },
        clickOnElement('Add to cart', '#add_to_cart'),
        {
            content: "Verify unchanged Rental Product period",
            trigger: '.o_renting_duration:first:contains("1")',
        },
    ],
});
