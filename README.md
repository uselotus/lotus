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

![Lotus Logo](./design_resources/Logo1.1-total-black.png#gh-dark-mode-only)
![Lotus Logo](./design_resources/Lotus-Horizontal-Logo-RGB-Black-Medium.svg#gh-light-mode-only)

# Lotus: Pricing & Packaging Infrastructure For Any Business Model

## Usage-Based, Per-Seat, Bespoke Enterprise Plans And More

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

Lotus is a pricing and billing engine that enables SaaS companies to deploy, monitor, and experiment with custom subscriptions and complex models like usage-based pricing.

<br/>

Lotus provides a flexible and modular control panel on top of your existing quote to cash stack that allows you to integrate data from multiple systems to help you figure out the optimal pricing scheme for your products.

<br/>

[Website](https://www.uselotus.io/) · [Issues](https://github.com/uselotus/lotus/issues) · [Docs](https://docs.uselotus.io/docs/overview/why-lotus) · [Contact Us](founders@uselotus.io)

<br/>

<!-- GETTING STARTED -->

## Getting Started

There are a few ways to use Lotus. After you set it up, head over to the [Docs](https://docs.uselotus.io/docs/overview/why-lotus) to learn how to use Lotus!

### :cloud: Cloud Version

Test out Lotus with a demo account [here](https://demo.uselotus.io/register).

The cloud version is best for convenience and fast deployment. This version also gets access to features faster than the self-hosted version.

Sign up for our `beta` [here](https://dsl2wm77apy.typeform.com/to/pehx2YSQ?typeform-source=www.uselotus.io) or email us at founders@uselotus.io for more details.

### :bust_in_silhouette: Self-Hosted Version

Best if you want to keep your data local or want full control and extensibility.

#### :computer: Local Instance

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Clone the repo and navigate to the project
   ```sh
   git clone https://github.com/uselotus/lotus.git && cd lotus
   ```
3. Run the self-hosting script:
   ```sh
    ./scripts/self-host.sh
   ```
   If you need to give the script permission to run, run `chmod 755 ./scripts/self-host.sh` first.
4. You should now be able to access the homepage at [localhost/](http://localhost/), and sign in using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` you defined, or the default, which is:
   ```py
   username: change_me
   password: change_me
   ```

Optionally:

- Change the environment variables located in `env/.env.prod` to suit your needs. For more details, check out [this guide in our docs](https://docs.uselotus.io/docs/overview/self-hosting).

Easy deployment options for AWS, GCP, and Azure are on the roadmap. If you have any questions, feel free to reach out to us.

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

Pricing your SaaS product is never easy, and often isn't directly related to the value you provide. Lotus was built to help you solve those problems and maintain the flexibility you need as you grow. Pricing is an underappreciated but hugely important lever for growth, and pushing it to the side can be a huge mistake. As companies evolve their pricing models, maintaining and scaling a pricing and billing stack can take significant engineering hours. With Lotus, you can go through the pricing deployment, monitoring, and experimentation cycle blazingly fast, while integrating with your existing payments, customer management, and data solutions.

Tech Stack:

- React Typescript
- Postgres (Timescaledb)
- Redpanda
- Redis
- Python (Django/Fast API)
- Celery (background jobs)

### Features

- **Usage-Based Pricing and Flexible Prorations** - Create custom pricing schemes for your SaaS, PaaS, IaaS, or any other acronym you come up with. A variety of models are supported out of the box, but with our fully extensible framework, creating exactly what you need is easy.

- **Sensible, Intuitive Plan Management** - Forget about keeping track of subscriptions, plans, versioning, deployments, and everything that gets in the way of your product. Lotus simplifies plan management for you and your engineering team, so you can focus on what matters.

- **Powerful Tools for Experimentation** - Lotus provides a suite of tools to empower you to change and deploy your pricing experiments and evaluate the effects it has on your business. Whether that's a backtest, an A/B test, or a forecast, we've got you covered.

- **Seamless Integrations with your Monetization Stack** - Never feel locked into a single system thanks to a variety of integrations to help you get the most out of your existing stack. Additionally, a simple yet expressive API helps you integrate with any system you want.

- **Cloud or Self-Hosted** - Apart from a managed cloud offering, Lotus provides a self-hosted version so you can keep your data local and have full control over your pricing.

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

Email Us: founders@uselotus.io

Message Us on Slack: <a href="https://join.slack.com/t/lotus-community/shared_invite/zt-1ghi61p9j-ADYbp3tEL~N16AxQr2mlzA"><img src="https://img.shields.io/badge/slack-lotus-E01E5A.svg?logo=slack&labelColor=2EB67D" alt="Join Lotus on Slack"></a>

Or visit www.uselotus.io

<p align="right">(<a href="#lotus-pricing-and-billing-on-any-metric">back to top</a>)</p>
