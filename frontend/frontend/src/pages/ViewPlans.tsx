import React, { FC } from "react";
import { Card, Col, Row } from "antd";

const Dashboard: FC = () => {
  return (
    <div className="site-card-wrapper">
      <Row gutter={16}>
        <Col span={8}>
          <Card title="Card title" bordered={false}>
            Starter Plan
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Card title" bordered={false}>
            Starter Plan
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Card title" bordered={false}>
            Pro Plan
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
