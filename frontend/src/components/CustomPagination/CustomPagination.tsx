import React, { FC } from "react";
import {
  RightOutlined,
  LeftOutlined,
  DoubleLeftOutlined,
} from "@ant-design/icons";
import "./CustomPagination.css";

interface CustomPaginationProps {
  cursor: string;
  rightCursor?: string;
  previous: string;
  next: string;
  currentPage: number;
  handleMovements: (value: "LEFT" | "RIGHT" | "START") => void;
}

const CustomPagination: FC<CustomPaginationProps> = ({
  cursor,
  rightCursor,
  currentPage,
  handleMovements,
  previous,
  next,
}) => {
  React.useLayoutEffect(() => {
    if (currentPage === 1) {
      handleMovements("START");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage]);
  return (
    <div className="flex justify-center space-x-4">
      <button
        type="button"
        disabled={!cursor || currentPage === 1}
        className="movementButton"
        onClick={() => handleMovements("START")}
      >
        <DoubleLeftOutlined />
      </button>
      <button
        type="button"
        className="movementButton"
        disabled={previous === "null" || cursor === ""}
        onClick={() => handleMovements("LEFT")}
      >
        <LeftOutlined />
      </button>
      <div className="currentPageNumber"> {currentPage} </div>
      <button
        type="button"
        className="movementButton"
        disabled={next === "null" || rightCursor === "RIGHT-END"}
        onClick={() => handleMovements("RIGHT")}
      >
        <RightOutlined />
      </button>
    </div>
  );
};

export default CustomPagination;
