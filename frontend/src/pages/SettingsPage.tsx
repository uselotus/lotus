import React, { FC } from "react";
import { Card, Col, Row, Tabs } from "antd";
import IntegrationsTab from "../components/Settings/settings/tabs/IntegrationsTab";
import { DeveloperTab } from "../components/Settings/settings/tabs/DeveloperTab";
import TeamTab from "../components/Settings/settings/tabs/TeamTab";
import { PageLayout } from "../components/base/PageLayout";
import ActivityStream from "../components/Settings/settings/tabs/ActivityTab";
import { Typography } from "antd";
import { Outlet, useNavigate } from "react-router-dom";

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

const SettingsPage: FC = () => {
  const navigate = useNavigate();

  const changeRoute = (key: string) => {
    navigate(`/settings/${key}`);
  };

  return (
    <PageLayout title="Settings">
      <Tabs
        size="large"
        onChange={(key) => {
          changeRoute(key);
        }}
        defaultActiveKey="general"
      >
        {tabItems.map((item) => (
          <Tabs.TabPane tab={item.tab} key={item.key}>
            <Outlet />
          </Tabs.TabPane>
        ))}
      </Tabs>
    </PageLayout>
  );
};

export default SettingsPage;
