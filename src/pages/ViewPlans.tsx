import React, { FC, useEffect, useState } from "react";
import { Avatar, Divider, List, Skeleton, Button, Card } from "antd";
import InfiniteScroll from "react-infinite-scroll-component";
import { Plan } from "../api/api";
import { PlanType } from "../types/plan-type";
import PlanDisplayBasic from "../components/PlanDisplayBasic";
import { useNavigate } from "react-router-dom";

const ViewPlans: FC = () => {
  const [plans, setPlans] = useState<PlanType[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    Plan.getPlans().then((data) => {
      setPlans(data);
    });
  }, []);

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  const [loading, setLoading] = useState(false);

  return (
    <div>
      <div className="flex flex-row w-full">
        <h1 className="text-3xl font-main">Plans</h1>
        <Button
          type="primary"
          className="ml-auto bg-info"
          onClick={navigateCreatePlan}
        >
          Create Plan
        </Button>
      </div>
      <br />
      <div
        id="scrollableDiv"
        style={{
          overflow: "auto",
          padding: "0 16px",
          border: "1px solid rgba(140, 140, 140, 0.35)",
        }}
      >
        <List
          bordered={false}
          dataSource={plans}
          className="w-full"
          renderItem={(item) => (
            <List.Item key={item.name}>
              <PlanDisplayBasic plan={item} />
            </List.Item>
          )}
        />
      </div>
    </div>
  );
};

export default ViewPlans;
