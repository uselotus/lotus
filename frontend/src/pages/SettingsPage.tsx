// @ts-ignore
import React, {FC, useEffect} from "react";
import { Tabs } from "antd";
import IntegrationsTab from "../components/Settings/settings/tabs/IntegrationsTab";
import { DeveloperTab } from "../components/Settings/settings/tabs/DeveloperTab";
import TeamTab from "../components/Settings/settings/tabs/TeamTab";
import { PageLayout } from "../components/base/PageLayout";
import ActivityStream from "../components/Settings/settings/tabs/ActivityTab";
import { useNavigate } from "react-router-dom";
<<<<<<< HEAD
import {useParams} from "react-router";
=======
import {useParams} from "react-router-dom";
>>>>>>> 76370693dfab7a587397589016fe050c4a679cd5
import GeneralTab from "../components/Settings/settings/tabs/GeneralTab";

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
              return <GeneralTab/>
          case "Integrations":
              return <IntegrationsTab/>
          case "Team":
              return <TeamTab/>
          case "Activity":
              return <ActivityStream/>
          case "Developer Settings":
              return <DeveloperTab/>
          default:
              return <GeneralTab/>
      }
  }

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
