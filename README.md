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

# Lotus: Pricing & Packaging Optimization

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
<p align="center">
   <a href='http://makeapullrequest.com'><img alt='PRs Welcome' src='https://img.shields.io/badge/PRs-welcome-43AF11.svg?style=shields'/></a>
   <a href="#contributors"><img src="https://img.shields.io/github/contributors/uselotus/lotus.svg?color=c0c8d0"></a>
   <a href="https://github.com/uselotus/lotus/stargazers"><img src="https://img.shields.io/github/stars/uselotus/lotus?color=e4b442" alt="Github Stars"></a>
   <a href="https://join.slack.com/t/lotus-community/shared_invite/zt-1ghi61p9j-ADYbp3tEL~N16AxQr2mlzA"><img src="https://img.shields.io/badge/slack-lotus-E01E5A.svg?logo=slack&labelColor=2EB67D" alt="Join Lotus on Slack"></a>
   <a href="https://github.com/uselotus/lotus/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-9d2235" alt="License"></a>
   <a href="https://github.com/uselotus/lotus/commits/main"><img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/uselotus/lotus?color=8b55e3"/></a>
   <a href="https://github.com/uselotus/lotus/actions/workflows/django-postgres.yml"><img alt="Build Passing" src="https://github.com/uselotus/lotus/actions/workflows/django-postgres.yml/badge.svg?style=flat"/></a>
   <a href="https://twitter.com/uselotusio"><img src="https://img.shields.io/twitter/follow/uselotusio?style=flat&color=1DA1F2"></a>
</p>


<!-- ALL-CONTRIBUTORS-BADGE:END -->

<br/>

Lotus is an open-core pricing engine. We enable SaaS companies to deploy, monitor, and experiment with custom subscription and complex models like usage-based pricing.

<br/>

We provide a flexible and modular control panel ontop of your existing quote to cash stack that joins data from multiple systems to help you figure out the optimal pricing scheme for your products.

<br/>

[Website](https://www.uselotus.io/) · [Issues](https://github.com/uselotus/lotus/issues) · [Docs](https://docs.uselotus.io/docs/intro) · [Contact Us](founders@uselotus.io)

<br/>

<!-- GETTING STARTED -->
## Getting Started

There are a few ways to use Lotus. After you set it up, head over to the [Docs](https://docs.uselotus.io/docs/lotus-docs) to learn how to use Lotus!

### :cloud: Cloud Version

Best for convenience and fast deployment. This version also gets access to features faster than the self-hosted version.

Sign up for our `alpha` [here](https://dsl2wm77apy.typeform.com/to/pehx2YSQ?typeform-source=www.uselotus.io) or email us at founders@uselotus.io for more details. 

### :bust_in_silhouette: Self-Hosted Version

Best if you want to keep your data local or want full control and extensibility.

#### :computer: Local Hobby Instance
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Clone the repo and navigate to the project
   ```sh
   git clone https://github.com/uselotus/lotus.git && cd lotus
   ```
3. Change the environemnt variables located in `env/.env.prod.example` to suit your needs. If you need help you can check out [this guide in our docs](https://uselotus.stoplight.io/docs/lotus-docs/branches/main/ylqsg3i42dd5z-docker-self-host-env).
4. Rename `env/.env.prod.example` to `env/.env.prod`. Make sure you don't commit your secret environment variables anywhere!
5. Build and run the Docker Image!
   ```sh
   docker-compose -f docker-compose.prod.yaml up --build
   ```
You should now be able to access the homepage at [localhost/](http://localhost/), and sign in using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` you defined.

We are currently working on easy deployment options for AWS, GCP, and Azure. If you have any questions, feel free to reach out to us.

<p align="right">(<a href="#lotus-pricing-and-billing-on-any-metric">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing
Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please [fork the repo](https://github.com/uselotus/lotus) and [create a pull request](https://makeapullrequest.com/). You can also simply [request a feature](https://github.com/uselotus/lotus/issues/new?assignees=&labels=&template=feature_request.md&title=).

Don't forget to give the project a star! Thanks again!

### :construction_worker: Local Development
To set up Lotus for development locally, please refer to our guide [here](https://docs.uselotus.io/docs/contributing). Whether you want to contribute something for the whole community to use, or you want to personalize Lotus for your own needs, our developer-friendly codebase makes it easy to get started.

<!-- ABOUT THE PROJECT -->
## About The Project

Lotus is the quickest way to bill flexibly and experiment with pricing. Our founders studied at MIT together and went on to DE Shaw and Citadel before joining forces to allow SaaS companies to price products accurately. Our project is open source and free for self-hosting. We charge for our cloud version, enterprise support (SSO, advanced permissions), and extra custom features we will add to the code over time.

<p align="right">(<a href="#lotus-pricing-and-billing-on-any-metric">back to top</a>)</p>

## :bar_chart: Repo Activity
![Alt](https://repobeats.axiom.co/api/embed/408c31cc31b6650e1e5c00414ec4a77b0277cf99.svg "Repobeats analytics image")

<p align="right">(<a href="#lotus-pricing-and-billing-on-any-metric">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#lotus-pricing-and-billing-on-any-metric">back to top</a>)</p>

<!-- CONTACT -->
## Get in Touch

Lotus founders - founders@uselotus.io

Or visit www.uselotus.io

<p align="right">(<a href="#lotus-pricing-and-billing-on-any-metric">back to top</a>)</p>

## Contributors

<a href = "https://github.com/uselotus/lotus/graphs/contributors">
  <img src = "https://contrib.rocks/image?repo=uselotus/lotus"/>
</a>
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

