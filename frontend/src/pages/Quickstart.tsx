import React, { FC, useState, useEffect } from "react";
import { PageLayout } from "../components/base/PageLayout";
import { Button } from "antd";
import { useQuery } from "react-query";
import {
  Events,
  APIKey,
  Metrics,
  Plan,
  Webhook,
  PaymentProcessorIntegration,
} from "../api/api";

interface Props {
  text: string;
  subText: string;
  complete: boolean;
  icon: string;
  time: string;
  userAction?: string;
  link?: string;
}

interface QuickStartCheckProps {
  setHasAPIKey?: (value: boolean) => void;
  setHasTrackedEvent?: (value: boolean) => void;
  setHasCreatedMetric?: (value: boolean) => void;
  setHasCreatedPlan?: (value: boolean) => void;
  setHasPaymentConnected?: (value: boolean) => void;
  setUsersInOrg?: (value: boolean) => void;
}

const quickStartCheck = async ({
  setHasAPIKey,
  setHasTrackedEvent,
  setHasCreatedMetric,
  setHasCreatedPlan,
  setHasPaymentConnected,
  setUsersInOrg,
}: QuickStartCheckProps) => {
  // Check if user has created a metric
  try {
    const apiKeys = await APIKey.getKeys();

    if (apiKeys && apiKeys.length > 0 && setHasAPIKey) {
      setHasAPIKey(true);
    }
  } catch (error) {
    console.log("Error fetching API keys:", error);
  }

  // Check if user has created an event
  try {
    const response = await Events.getEventPreviews("");
    const eventData = response;

    if (
      eventData &&
      eventData.results &&
      eventData.results.length > 0 &&
      setHasTrackedEvent
    ) {
      setHasTrackedEvent(true);
    }
  } catch (error) {
    console.log("Error fetching event data:", error);
  }

  // Check if user has created a metric
  try {
    const metrics = await Metrics.getMetrics();
    console.log("metrics", metrics);

    if (metrics && metrics.length > 0 && setHasCreatedMetric) {
      setHasCreatedMetric(true);
    }
  } catch (error) {
    console.log("Error fetching metrics:", error);
  }

  // Check if user has created a plan
  try {
    const plans = await Plan.getPlans();

    if (plans && plans.length > 0 && setHasCreatedPlan) {
      setHasCreatedPlan(true);
    }
  } catch (error) {
    console.log("Error fetching plans:", error);
  }

  // Check if user has connected a payment method or hooked up to a webhook for invoice.created
  try {
    const paymentProcessors =
      await PaymentProcessorIntegration.getPaymentProcessorConnectionStatus();
    if (
      paymentProcessors &&
      paymentProcessors.length > 0 &&
      setHasPaymentConnected
    ) {
      for (let i = 0; i < paymentProcessors.length; i++) {
        if (paymentProcessors[i].connected) {
          setHasPaymentConnected(true);
          break;
        }
      }
      const webhooks = await Webhook.getEndpoints();
      if (webhooks && webhooks.length > 0 && setHasPaymentConnected) {
        setHasPaymentConnected(true);
      }
    }
  } catch (error) {
    console.log("Error fetching payment processors:", error);
  }
};

const quickStartItem = ({
  text,
  subText,
  complete,
  icon,
  time,
  userAction,
  link,
}: Props): JSX.Element => {
  if (link) {
    return (
      <a
        target={`${link.includes("https") ? "_blank" : "_self"}`}
        rel="noopener noreferrer"
        className={`w-full ${
          complete && "opacity-30 hover:opacity-100 duration-200"
        }`}
        href={link}
      >
        <div
          onKeyDown={() => null}
          role="button"
          tabIndex={0}
          className="relative group bg-gray-300 hover:bg-gold  duration-200 rounded-md border pl-2 pr-6 py-2 h-[5.5rem] w-full flex items-center justify-between overflow-hidden mb-3 cursor-pointer"
        >
          <div className="flex flex-row items-center mr-4">
            <i className={"text-4xl mx-2 w-16" + icon} />
            {complete && (
              <div className="bg-bunker-500 group-hover:bg-gold w-7 h-7 rounded-full absolute left-12 top-10 p-2 flex items-center justify-center">
                <i className="ri-checkbox-circle-fill"></i>
              </div>
            )}
            <div className="flex flex-col items-start">
              <div className="text-xl font-semibold mt-0.5">{text}</div>
              <div className="text-sm font-normal">{subText}</div>
            </div>
          </div>
          <div
            className={`pr-4 font-semibold text-sm w-28 text-right ${
              complete && "text-primary"
            }`}
          >
            {complete ? "Complete!" : `About ${time}`}
          </div>
          {complete && (
            <div className="absolute bottom-0 left-0 h-1 w-full bg-primary" />
          )}
        </div>
      </a>
    );
  }
  return (
    <div
      onKeyDown={() => null}
      role="button"
      tabIndex={0}
      className="relative bg-bunker-700 hover:bg-bunker-500 shadow-xl duration-200 rounded-md border border-dashed border-bunker-400 pl-2 pr-6 py-2 h-[5.5rem] w-full flex items-center justify-between overflow-hidden my-1.5 cursor-pointer"
    >
      <div className="flex flex-row items-center mr-4">
        <i className={"text-4xl mx-2 w-16" + icon} />

        {complete && (
          <div className="bg-bunker-700 w-7 h-7 rounded-full absolute left-11 top-10">
            <i className="ri-checkbox-circle-fill"></i>
          </div>
        )}
        <div className="flex flex-col items-start">
          <div className="text-xl font-semibold mt-0.5">{text}</div>
          <div className="text-sm font-normal mt-0.5">{subText}</div>
        </div>
      </div>
      <div
        className={`pr-4 font-semibold text-sm w-28 text-right ${
          complete && "text-primary"
        }`}
      >
        {complete ? "Complete!" : `About ${time}`}
      </div>
      {complete && (
        <div className="absolute bottom-0 left-0 h-1 w-full bg-primary" />
      )}
    </div>
  );
};

const QuickstartPage: FC = () => {
  const [hasAPIKey, setHasAPIKey] = useState(false);
  const [hasTrackedEvent, setHasTrackedEvent] = useState(false);
  const [hasCreatedMetric, setHasCreatedMetric] = useState(false);
  const [hasCreatedPlan, setHasCreatedPlan] = useState(false);
  const [hasPaymentConnected, setHasPaymentConnected] = useState(false);
  const [usersInOrg, setUsersInOrg] = useState(false);

  useEffect(() => {
    quickStartCheck({
      setHasAPIKey,
      setHasTrackedEvent,
      setHasCreatedMetric,
      setHasCreatedPlan,
      setHasPaymentConnected,
      setUsersInOrg,
    });
  }, []);
  return (
    <PageLayout title="Get Started Fast" extra={[]}>
      <div>
        <div className="flex relative flex-col items-center text-lg mx-auto px-6 max-w-3xl lg:max-w-4xl xl:max-w-5xl py-6">
          <div className="text-4xl font-bold text-left w-full mt-12">
            Your quick start guide
          </div>
          <div className="text-lg text-left w-full pt-2 pb-4 mb-14 text">
            Click on the items below and follow the instructions.
          </div>

          {quickStartItem({
            text: "Create an API Key",
            subText: "",
            complete: hasAPIKey,
            icon: "faHandPeace",
            time: "30 sec",
            userAction: "intro_cta_clicked",
            link: `/settings/developer-settings`,
          })}
          {/* {learningItem({
            text: "Add your secrets",
            subText: "Click to see example secrets, and add your own.",
            complete: hasUserPushedSecrets,
            icon: faPlus,
            time: "2 min",
            userAction: "first_time_secrets_pushed",
            link: `/dashboard/${router.query.id}`,
          })}
          <div className="relative group bg-bunker-500 shadow-xl duration-200 rounded-md border border-mineshaft-600 pl-2 pr-2 pt-4 pb-2 h-full w-full flex flex-col items-center justify-between overflow-hidden mb-3 cursor-default">
            <div className="w-full flex flex-row items-center mb-4 pr-4">
              <div className="flex flex-row items-center mr-4 w-full">
                <FontAwesomeIcon
                  icon={faNetworkWired}
                  className="text-4xl mx-2 w-16"
                />
                {false && (
                  <div className="bg-bunker-500 group-hover:bg-mineshaft-700 w-7 h-7 rounded-full absolute left-12 top-10 p-2 flex items-center justify-center">
                    <FontAwesomeIcon
                      icon={faCheckCircle}
                      className="text-4xl w-5 h-5 text-green"
                    />
                  </div>
                )}
                <div className="flex pl-0.5 flex-col items-start">
                  <div className="text-xl font-semibold mt-0.5">
                    Inject secrets locally
                  </div>
                  <div className="text-sm font-normal">
                    Replace .env files with a more secure and efficient
                    alternative.
                  </div>
                </div>
              </div>
              <div
                className={`pr-4 font-semibold text-sm w-28 text-right ${
                  false && "text-green"
                }`}
              >
                About 2 min
              </div>
            </div>
            <TabsObject />
            {false && (
              <div className="absolute bottom-0 left-0 h-1 w-full bg-green" />
            )}
          </div> */}

          {quickStartItem({
            text: "Track your first event",
            subText: "",
            complete: hasTrackedEvent,
            icon: "ri-user-add-line",
            time: "3 min",
          })}
          {quickStartItem({
            text: "Create a Metric",
            subText: "Use a template provide for the quickest start.",
            complete: hasCreatedMetric,
            icon: "ri-user-add-line",
            time: "1 min",
            link: `/metrics`,
          })}
          {quickStartItem({
            text: "Create a Plan",
            subText: "",
            complete: hasCreatedPlan,
            icon: "ri-user-add-line",
            time: "2 min",
            link: `/plans/create-plan`,
          })}
          {quickStartItem({
            text: "Connect a payment method or a webhook endpoint",
            subText:
              "Ensure that you have a way to collect payment for invoices that are generated in Lotus, either through Stripe, Braintree, or your own integration built ontop of our webhooks.",
            complete: hasPaymentConnected,
            icon: "ri-user-add-line",
            time: "2 min",
            link: `/settings/integrations`,
          })}
          {quickStartItem({
            text: "Join Lotus Slack",
            subText:
              "Ask any specific or general questions in our community Slack!",
            complete: false,
            icon: "ri-slack-line",
            time: "1 min",
            userAction: "slack_cta_clicked",
            link: "https://join.slack.com/t/lotus-community/shared_invite/zt-1fufuktbp-ignnw768aZgdFNlcvAOSrw",
          })}
          {quickStartItem({
            text: "Star Lotus on GitHub",
            subText: "Want to show some open-source love? Give us a star! :)",
            complete: false,
            icon: "ri-star-line",
            time: "1 min",
            userAction: "star_cta_clicked",
            link: "https://github.com/uselotus/lotus",
          })}
        </div>
      </div>
    </PageLayout>
  );
};

export default QuickstartPage;
