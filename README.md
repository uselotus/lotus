<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a name="readme-top"></a>
<!--



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
<!-- [![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url] -->



<!-- PROJECT LOGO -->
![Lotus Logo](./design_resources/Lotus-Horizontal-Logo-RGB-Black-Medium.jpg#gh-dark-mode-only)
![Lotus Logo](./design_resources/Lotus-Horizontal-Logo-RGB-Black-Medium.svg#gh-light-mode-only)

# :lotus: Lotus: Pricing and Billing On Any Metric

<br/>

Lotus is the open-core pricing and billing engine. We enable SaaS companies to manage and experiment in real-time with custom subscription and usage-based billing.

<br/>

We provide a flexible and modular approach to every step of the billing experience, from metering to invoicing to helping you understand the optimal pricing scheme for your product.

<br/>

[Website](https://www.uselotus.io/) · [Issues](https://github.com/uselotus/lotus/issues) · [Docs](https://docs.uselotus.io/docs/lotus-docs) · [Contact Us](founders@uselotus.io)

<br/>

<!-- GETTING STARTED -->
## Getting Started

There's a few ways to use Lotus. After you set it up, head over to the [Docs](https://docs.uselotus.io/docs/lotus-docs) to learn how to use Lotus!

### :cloud: Cloud Version

Best for convenience and fast deployment. 

Sign up for our `alpha` [here](https://dsl2wm77apy.typeform.com/to/pehx2YSQ?typeform-source=www.uselotus.io) or email us at founders@uselotus.io for more details. 

Once you have an account, head over to [the app](https://www.uselotus.app/) and you can start using Lotus right away.

### Self-Hosted Version

Best if you want to keep your data local or want full control and extensibility.

#### :pisces: One-click Deploy with Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

#### :computer: Set up locally

1. Clone the repo and navigate to the project
   ```sh
   git clone https://github.com/uselotus/lotus.git && cd lotus
   ```
2. Create the necessary environment variables by following [this guide in our docs](https://uselotus.stoplight.io/docs/lotus-docs/branches/main/ylqsg3i42dd5z-docker-self-host-env).
3. Build the Docker Image 
   ```sh
   export DOCKER_BUILDKIT=0 && 
   docker-compose -f docker-compose.prod.yaml build
   ```
4. Run the Docker Image!
   ```sh
   docker-compose --env-file env/.env -f docker-compose.prod.yaml up
   ```
You should now be able to access the homepage at [localhost/](http://localhost/), and sign in using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` you defined.

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>

<!-- USAGE EXAMPLES -->
## Examples

_For more examples, please refer to the [Documentation](https://uselotus.stoplight.io/)_

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply [request a feature]().
Don't forget to give the project a star! Thanks again!

### :exclamation: Local Development
In order to develop locally, we recommend using Docker to set up the environment, which allows for hot reloading of both frontend and backend code.
1. Clone the repo and navigate to the project
   ```sh
   git clone https://github.com/uselotus/lotus.git && cd lotus
   ```
2. Create the necessary environment variables by following [this guide in our docs](https://uselotus.stoplight.io/docs/lotus-docs/branches/main/ylqsg3i42dd5z-docker-self-host-env).
3. Build the Docker Image 
   ```sh
   export DOCKER_BUILDKIT=0 && 
   docker-compose -f docker-compose.dev.yaml build
   ```
4. Run the Docker Image!
   ```sh
   docker-compose --env-file env/.env.dev -f docker-compose.dev.yaml up
   ```
You should now be able to access the homepage at [localhost:8000/](http://localhost:8000/), and sign in using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` you defined.

If you make any changes to the backend settings, you might need to restart the Docker container.

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>

<!-- ABOUT THE PROJECT -->
## About The Project

Lotus is the quickest way to start billing flexibly and experiment with pricing. Our founders studied at MIT together and went on to DE Shaw and Citadel before joining forces to allow SaaS companies to price products accurately. Our metering and billing solutions are open source and free for self-hosting. We charge for our cloud version, enterprise support (SSO, advanced permissions), and extra custom features we will add to the code over time.

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>

## :bar_chart: Repo Activity
![Alt](https://repobeats.axiom.co/api/embed/408c31cc31b6650e1e5c00414ec4a77b0277cf99.svg "Repobeats analytics image")

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>

<!-- CONTACT -->
## Get in Touch

Lotus founders - founders@uselotus.io

Or visit www.uselotus.io

<p align="right">(<a href="#lotus-pricing-and-billing-your-way">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/uselotus/lotus.svg?style=for-the-badge
[contributors-url]: [https://github.com/uselotus/lotus/graphs/contributors]
[forks-shield]: https://img.shields.io/github/forks/github_username/repo_name.svg?style=for-the-badge
[forks-url]: https://github.com/uselotus/lotus/network/members
[stars-shield]: https://img.shields.io/github/stars/uselotus/lotus.svg?style=for-the-badge
[stars-url]: https://github.com/uselotus/lotus/stargazers
[issues-shield]: https://img.shields.io/github/issues/github_username/repo_name.svg?style=for-the-badge
[issues-url]: https://github.com/github_username/repo_name/issues
[license-shield]: https://img.shields.io/github/license/github_username/repo_name.svg?style=for-the-badge
[license-url]: https://github.com/github_username/repo_name/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/uselotusio
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com
