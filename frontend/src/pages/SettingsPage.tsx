// @ts-ignore
import React, { FC, useEffect } from "react";
import { Tabs } from "antd";
import IntegrationsTab from "../components/Settings/settings/tabs/IntegrationsTab";
import { DeveloperTab } from "../components/Settings/settings/tabs/DeveloperTab";
import TeamTab from "../components/Settings/settings/tabs/TeamTab";
import { PageLayout } from "../components/base/PageLayout";
import ActivityStream from "../components/Settings/settings/tabs/ActivityTab";
import { useNavigate } from "react-router-dom";
import { useParams } from "react-router-dom";
import GeneralTab from "../components/Settings/settings/tabs/GeneralTab";
import CreatePricingUnit from "../components/Settings/settings/tabs/CreatePricingUnitTab";

const tabItems = [
  {
    key: "general",
    tab: "General",
  },
  {
    key: "integrations",
    tab: "Integrations",
  },
  {
    key: "team",
    tab: "Team",
  },
  {
    key: "activity",
    tab: "Activity",
  },
  {
    key: "developer-settings",
    tab: "Developer Settings",
  },
  // {
  //   key: "create-pricing-units",
  //   tab: "Create Pricing Units",
  // },
  // {
  //   key: "billing",
  //   tab: "Billing",
  // },
];

type SettingTabParams = {
  tab: string;
};

const SettingsPage: FC = () => {
  const navigate = useNavigate();
  const { tab } = useParams<SettingTabParams>();

  const changeRoute = (key: string) => {
    navigate(`/settings/${key}`);
  };

  const getCurrentTab = (currentTab) => {
    switch (currentTab) {
      case "General":
        return <GeneralTab />;
      case "Integrations":
        return <IntegrationsTab />;
      case "Team":
        return <TeamTab />;
      // case "Activity":
      //   return <ActivityStream />;
      case "Developer Settings":
        return <DeveloperTab />;
      case "Create Pricing Units":
        return <CreatePricingUnit />;
      default:
        return <GeneralTab />;
    }
  };

  return (
    <PageLayout title="Settings">
      <Tabs
        size="large"
        onChange={(key) => changeRoute(key)}
        activeKey={tab ? tab : "general"}
        defaultActiveKey="general"
      >
        {tabItems.map((item) => (
          <Tabs.TabPane tab={item.tab} key={item.key}>
            {getCurrentTab(item.tab)}
          </Tabs.TabPane>
        ))}
      </Tabs>
    </PageLayout>
  );
};

export default SettingsPage;
