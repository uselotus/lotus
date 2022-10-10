import React, { FC } from "react";
import { Card, Col, Row, Tabs } from "antd";
import IntegrationsTab from "./IntegrationsTab";
import { PageLayout } from "../../components/base/PageLayout";

const SettingsPage: FC = () => {
  return (
    <PageLayout title="Settings">
      <Tabs>
        <Tabs.TabPane tab="Profile" key="profile">
          Profile
        </Tabs.TabPane>
        <Tabs.TabPane tab="Integrations" key="integrations">
          <IntegrationsTab />
        </Tabs.TabPane>
        <Tabs.TabPane tab="Team" key="team">
          Content 3
        </Tabs.TabPane>
        <Tabs.TabPane tab="Developer Settings" key="developer-settings">
          Content 4
        </Tabs.TabPane>
      </Tabs>
    </PageLayout>
  );
};

export default SettingsPage;
