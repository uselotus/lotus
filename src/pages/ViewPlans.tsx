import React, { FC, useEffect, useState } from "react";
import { Avatar, Divider, List, Skeleton } from "antd";
import InfiniteScroll from "react-infinite-scroll-component";
import { Plan } from "../api/api";
import { PlanType } from "../types/plan-type";
import PlanDisplayBasic from "../components/PlanDisplayBasic";

const ViewPlans: FC = () => {
  const [plans, setPlans] = useState<PlanType[]>([]);

  useEffect(() => {
    Plan.getPlans().then((data) => {
      setPlans(data);
    });
  }, []);

  const [loading, setLoading] = useState(false);

  return (
    <div>
      <h1 className="text-3xl font-main">Plans</h1>
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
