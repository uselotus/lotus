import React, { FC, useEffect, useState } from "react";
import { Avatar, Divider, List, Skeleton, Button } from "antd";
import InfiniteScroll from "react-infinite-scroll-component";
import { useNavigate } from "react-router-dom";

const ViewMetrics: FC = () => {
  const navigate = useNavigate();

  useEffect(() => {}, []);

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  const [loading, setLoading] = useState(false);

  return (
    <div>
      <div className="flex flex-row w-full">
        <h1 className="text-3xl font-main">Billable Metrics</h1>
        <Button
          type="primary"
          className="ml-auto bg-info"
          onClick={navigateCreatePlan}
        >
          Create Metric
        </Button>
      </div>
    </div>
  );
};

export default ViewMetrics;
