import React, { FC, useEffect, useState } from "react";
import { Card, Col, Row, List } from "antd";
import { Plan } from "../api/api";
import { PlanType } from "../types/plan-type";

const ViewPlans: FC = () => {
  const [plans, setPlans] = useState<PlanType[]>([]);

  useEffect(() => {
    Plan.getPlans().then((data) => {
      console.log(data);
      setPlans(data);
    });
  }, []);

  return (
    <div>
      <h1 className="bg-grey1">Plans</h1>
      <br />
      {plans.length === 0 && <p>No Plans</p>}
      <div className="site-card-wrapper">
        <Row gutter={18}>
          {plans.map((plan, k) => (
            <Col key={k} span={6}>
              <Card title={plan.name} bordered={true}>
                <p>{plan.description}</p>
                <p>Billing Interval: {plan.billing_interval}</p>
                <p>
                  Subscription Rate: ${plan.flat_rate}/{plan.billing_interval}
                </p>
                <List
                  bordered={true}
                  itemLayout="horizontal"
                  dataSource={plan.components}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta
                        title={item.metric_name}
                        description={
                          <div>
                            <p>
                              Aggregation type: {item.aggregation_type} over{" "}
                              {item.property_name}
                            </p>
                            <p>
                              Included Initial Amount:
                              <b>{item.free_metric_quantity}</b>
                            </p>
                            <p>
                              Then <b>${item.cost_per_metric}</b> per{" "}
                              <b>
                                {item.unit_per_cost} {item.metric_name}
                              </b>
                            </p>
                          </div>
                        }
                      />
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
          ))}
        </Row>
      </div>
    </div>
  );
};

export default ViewPlans;
