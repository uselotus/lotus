import React, { FC, useState, useEffect, useMemo } from "react";
import { PageLayout } from "../components/base/PageLayout";
import { useQuery } from "@tanstack/react-query";
import useGlobalStore from "../stores/useGlobalstore";
import quickStartCheck from "../helpers/quickStartCheck";
import { toast } from "react-toastify";
import SyntaxHighlighter from "react-syntax-highlighter";
import { docco } from "react-syntax-highlighter/dist/esm/styles/hljs";
import { CheckCircleOutlined, CopyOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";

interface Props {
  text: string;
  subText: string;
  complete: boolean;
  icon: string;
  time: string;
  userAction?: string;
  link?: string;
  highlighted?: boolean;
}

const CodeExample = ({ complete }: { complete: boolean }) => {
  const [selectedTab, setSelectedTab] = useState("curl");
  const [copySuccess, setCopySuccess] = useState(false);

  const codeExamples = {
    curl: {
      label: "Curl",
      language: "bash",
      code: `curl --request POST \
      --url https://api.uselotus.io/api/track/ \
      --header 'X-API-KEY: AUTH_VALUE' \
      --header 'Content-Type: application/json' \
      --data '{
      "batch": [
        {
          event_name: "test"
          time_created: "2023-03-21T21:26:43.545Z"
          customer_id: "cust_5894767364aa4e64"
          properties: { test: "test", numeric_quantity: 3.1415 }
          idempotency_id: "c2c5eb5d-de4b-44e0"
        },
      ]
    }'`,
    },
    pythonSDK: {
      label: "Python SDK",
      language: "python",
      code: `lotus.track_event(
        customer_id='customer123',
        event_name='api_call',
        properties={
            'region': 'US',
            'mb_used': 150
          },
        idempotency_id='c9799bf9-e5c9-4007-8d10-0663d045d23c',
        time_created="2023-01-01T21:58:14.193Z"
      )`,
    },
    typescriptSDK: {
      label: "TypeScript SDK",
      language: "typescript",
      code: `lotus.trackEvent({
        batch: [
          {
            event_name: "test", // required
            time_created: new Date(), // optional, if not provided current time will be taken
            customer_id: "cust_5894767364aa4e64", // required
            properties: { test: "test", numeric_quantity: 3.1415 }, //optional, pass in any additional properties you want to aggregate or measure
            idempotency_id: "c2c5eb5d-de4b-44e0", //optional if not provided Randomly generated ID will be taken
          },
        ],
      });`,
    },
  };

  const handleTabClick = (tab) => {
    setSelectedTab(tab);
  };

  const copyToClipBoard = async (copyMe) => {
    try {
      await navigator.clipboard.writeText(copyMe);
      setCopySuccess(true);
      setTimeout(() => {
        setCopySuccess(false);
      }, 3000);
    } catch (err) {
      setCopySuccess(false);
    }
  };

  return (
    <div className="p-4 pt-0 bg-[#F5F5F5] w-full">
      <div className="flex space-x-4 mb-12">
        {Object.keys(codeExamples).map((key) => (
          <button
            key={key}
            onClick={() => handleTabClick(key)}
            className={`px-4 py-2 text-white text-sm rounded-md ${
              selectedTab === key
                ? " bg-darkgold"
                : "bg-gray-500 hover:bg-gray-600"
            }`}
          >
            {codeExamples[key].label}
          </button>
        ))}
      </div>
      <div
        className={`relative rounded-md border p-4  ${
          complete ? "bg-[#E3FFF1]" : "bg-slate-100"
        }`}
      >
        <SyntaxHighlighter
          customStyle={{
            ...docco,
            marginBottom: "0px",
            background: "transparent",
            fontSize: "14px",
          }}
          language={codeExamples[selectedTab].language}
        >
          {codeExamples[selectedTab].code}
        </SyntaxHighlighter>
        <div className="absolute bottom-4 right-4 cursor-pointer">
          <Tooltip
            placement="right"
            title={
              copySuccess ? (
                <div className="copiedTag">
                  <CheckCircleOutlined className="checkedIcon" /> Copied
                </div>
              ) : (
                <span>Copy Code</span>
              )
            }
          >
            <CopyOutlined
              onClick={() => copyToClipBoard(codeExamples[selectedTab].code)}
            />
          </Tooltip>
        </div>
      </div>
    </div>
  );
};

function demoLink(link) {
  if ((import.meta as any).env.VITE_IS_DEMO === "true") {
    return "/";
  } else {
    return link;
  }
}

const quickStartItem = ({
  text,
  subText,
  complete,
  icon,
  time,
  link,
  highlighted,
}: Props): JSX.Element => {
  if (link) {
    return (
      <a
        target={`${link.includes("https") ? "_blank" : "_self"}`}
        rel="noopener noreferrer"
        className={`w-full ${complete && " hover:opacity-100 duration-150"}`}
        href={link}
      >
        <div
          onKeyDown={() => null}
          role="button"
          tabIndex={0}
          className={`relative group text-black  duration-200 rounded-md border pl-2 pr-6 py-2 h-[5.5rem] w-full flex items-center justify-between overflow-hidden mb-3 cursor-pointer ${
            complete ? "bg-[#E3FFF1]" : "bg-[#F5F5F5] "
          }
            ${highlighted && " border-2 border-b-8 border-[#BF9F79] "}
          `}
        >
          <div className="flex flex-row items-center mr-4 ml-4">
            <div className="flex flex-col items-start">
              <div className="text-xl font-semibold mt-0.5">{text}</div>
              <div className="text-sm font-normal">{subText}</div>
            </div>
          </div>
          <div
            className={`pr-4 font-semibold text-sm text-right ${
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
    <>
      <div
        onKeyDown={() => null}
        role="button"
        tabIndex={0}
        className={`relative group text-black duration-150 rounded-md border pl-2 pr-6 py-2 h-[5.5rem] w-full flex items-center justify-between overflow-hidden mb-3 ${
          complete ? "bg-[#E3FFF1]" : "bg-[#F5F5F5] "
        }
        ${highlighted && " border-2 border-b-8 border-[#BF9F79] "}

      `}
      >
        <div className="flex flex-row items-center mr-4 ml-4">
          <div className="flex flex-col items-start">
            <div className="text-xl font-semibold mt-0.5">{text}</div>
            <div className="text-sm font-normal mt-0.5">{subText}</div>
          </div>
        </div>
        <div
          className={`pr-4 font-semibold text-sm text-right ${
            complete && "text-primary"
          }`}
        >
          {complete ? "Complete!" : `About ${time}`}
        </div>
        {complete && (
          <div className="absolute bottom-0 left-0 h-1 w-full bg-primary" />
        )}
      </div>
      <CodeExample complete={complete} />
    </>
  );
};

const QuickstartPage: FC = () => {
  const [usersInOrg, setUsersInOrg] = useState(false);
  const [currentItem, setCurrentItem] = useState(0);
  const org = useGlobalStore((state) => state.org);
  const setQuickStartProgress = useGlobalStore(
    (state) => state.setQuickStartProgress
  );
  const {
    hasAPIKey,
    hasCreatedMetric,
    hasCreatedPlan,
    hasPaymentConnected,
    hasTrackedEvent,
  } = useGlobalStore((state) => state.quickStartProgress);

  useEffect(() => {
    quickStartCheck({ setQuickStartProgress });
  }, []);

  useEffect(() => {
    if (hasAPIKey && !hasTrackedEvent) {
      setCurrentItem(1);
    }
    if (hasAPIKey && hasTrackedEvent && !hasCreatedMetric) {
      setCurrentItem(2);
    }
    if (hasAPIKey && hasTrackedEvent && hasCreatedMetric && !hasCreatedPlan) {
      setCurrentItem(3);
    }
    if (
      hasAPIKey &&
      hasTrackedEvent &&
      hasCreatedMetric &&
      hasCreatedPlan &&
      !hasPaymentConnected
    ) {
      setCurrentItem(4);
    }
    if (
      hasAPIKey &&
      hasTrackedEvent &&
      hasCreatedMetric &&
      hasCreatedPlan &&
      hasPaymentConnected
    ) {
      setCurrentItem(5);
    }
  }, [
    hasAPIKey,
    hasTrackedEvent,
    hasCreatedMetric,
    hasCreatedPlan,
    hasPaymentConnected,
  ]);

  return (
    <PageLayout title="Quickstart" extra={[]}>
      <div>
        <div className="flex relative flex-col items-center text-lg mx-auto space-y-6 px-6 max-w-3xl lg:max-w-4xl xl:max-w-5xl py-6">
          <div className="text-4xl font-bold text-left w-full mt-12">
            {org?.organization_name}'s quick start guide
          </div>
          <div className="text-lg text-left w-full pt-2 pb-4 mb-14">
            Click on the items below and follow the instructions.
          </div>

          {quickStartItem({
            text: "1. Create an API Key",
            subText: "",
            complete: hasAPIKey,
            icon: "faHandPeace",
            time: "30 sec",
            userAction: "intro_cta_clicked",
            link: demoLink(`/settings/developer-settings`),
            highlighted: currentItem === 0,
          })}

          {quickStartItem({
            text: "2. Track your first event",
            subText: "",
            complete: hasTrackedEvent,
            icon: "ri-user-add-line",
            time: "3 min",
            highlighted: currentItem === 1,
          })}

          {quickStartItem({
            text: "3. Create a Metric",
            subText: "",
            complete: hasCreatedMetric,
            icon: "ri-user-add-line",
            time: "1 min",
            link: `/metrics`,
            highlighted: currentItem === 2,
          })}
          {quickStartItem({
            text: "4. Create a Plan",
            subText: "",
            complete: hasCreatedPlan,
            icon: "ri-user-add-line",
            time: "2 min",
            link: `/create-plan`,
            highlighted: currentItem === 3,
          })}
          {quickStartItem({
            text: "5. Connect a payment method or a webhook endpoint",
            subText:
              "Ensure that you have a way to collect payment for invoices.",
            complete: hasPaymentConnected,
            icon: "ri-user-add-line",
            time: "2 min",
            link: demoLink(`/settings/integrations`),
            highlighted: currentItem === 4,
          })}
          {quickStartItem({
            text: "6. Join Lotus Slack",
            subText:
              "Ask any specific or general questions in our community Slack!",
            complete: false,
            icon: "ri-slack-line",
            time: "1 min",
            userAction: "slack_cta_clicked",
            link: "https://join.slack.com/t/lotus-community/shared_invite/zt-1fufuktbp-ignnw768aZgdFNlcvAOSrw",
          })}
          {quickStartItem({
            text: "7. Star Lotus on GitHub",
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
