// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable, Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {IOracleAdapter} from "./interfaces/IOracleAdapter.sol";

/// @title OracleAdapter
/// @notice Reporter-signed index values, per-index calendar windows, finalize, void (SPEC section 9).
/// @dev Pausable is inherited for the uniform admin surface; pause gates nothing here because the
///      oracle carries no new risk and SPEC 15 forbids pausing finalize/settlement.
contract OracleAdapter is IOracleAdapter, Ownable2Step, Pausable, EIP712 {
    bytes32 public constant REPORT_TYPEHASH =
        keccak256("Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)");
    uint256 internal constant DAY = 86_400;

    uint64 public override maxReportAge;

    mapping(bytes32 => IndexConfig) internal _cfg;
    mapping(bytes32 => bool) public registered;
    mapping(address => bool) public isReporter;
    mapping(bytes32 => mapping(uint32 => Observation)) internal _obs;

    error AlreadyRegistered();
    error NotRegistered();
    error BadConfig();
    error IndexNotActive(); // P1
    error AlreadyFinal(); // P2
    error DayVoided(); // P2
    error AsOfBeforeFetch(); // P3
    error AsOfInFuture(); // P4
    error ReportStale(); // P5
    error WindowClosed(); // P6
    error RevisionNotNewer(); // P7
    error BadSigner(); // P8
    error TooEarly();
    error NothingPosted();
    error AlreadyPosted();
    error NotFinal();

    constructor(address owner_, uint64 maxReportAge_) Ownable(owner_) EIP712("wi-oracle", "1") {
        maxReportAge = maxReportAge_;
    }

    // ---- admin ----

    function registerIndex(bytes32 indexId, IndexConfig calldata cfg) external onlyOwner {
        if (registered[indexId]) revert AlreadyRegistered();
        if (cfg.disputeWindow == 0) revert BadConfig();
        registered[indexId] = true;
        _cfg[indexId] = cfg;
        emit IndexRegistered(indexId, cfg.fetchLag, cfg.disputeWindow, cfg.voidGrace);
        emit IndexActiveSet(indexId, cfg.active);
    }

    function setIndexActive(bytes32 indexId, bool active) external onlyOwner {
        if (!registered[indexId]) revert NotRegistered();
        _cfg[indexId].active = active;
        emit IndexActiveSet(indexId, active);
    }

    function setReporter(address reporter, bool allowed) external onlyOwner {
        isReporter[reporter] = allowed;
        emit ReporterSet(reporter, allowed);
    }

    function setMaxReportAge(uint64 age) external onlyOwner {
        maxReportAge = age;
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // ---- reports ----

    function post(
        bytes32 indexId,
        uint32 day,
        int64 value,
        uint16 revision,
        uint64 asOf,
        bytes32 vintageHash,
        bytes calldata signature
    ) external {
        IndexConfig memory c = _cfg[indexId];
        if (!registered[indexId] || !c.active) revert IndexNotActive();
        Observation storage o = _obs[indexId][day];
        if (o.finalized) revert AlreadyFinal();
        if (o.voided) revert DayVoided();
        uint256 fAt = _fetchAt(c, day);
        if (asOf < fAt) revert AsOfBeforeFetch();
        if (asOf > block.timestamp) revert AsOfInFuture();
        if (block.timestamp - asOf > maxReportAge) revert ReportStale();
        if (block.timestamp >= fAt + c.disputeWindow) revert WindowClosed();
        if (o.posted && revision <= o.revision) revert RevisionNotNewer();
        address signer = ECDSA.recover(_digest(indexId, day, value, revision, asOf), signature);
        if (!isReporter[signer]) revert BadSigner();
        o.value = value;
        o.revision = revision;
        o.asOf = asOf;
        o.posted = true;
        o.vintageHash = vintageHash;
        emit Posted(indexId, day, value, revision, asOf, signer, vintageHash);
    }

    function finalize(bytes32 indexId, uint32 day) external {
        Observation storage o = _obs[indexId][day];
        if (o.finalized) revert AlreadyFinal();
        if (!o.posted) revert NothingPosted();
        if (block.timestamp < _fetchAt(_cfg[indexId], day) + _cfg[indexId].disputeWindow) revert TooEarly();
        o.finalized = true;
        emit Finalized(indexId, day, o.value);
    }

    function voidDay(bytes32 indexId, uint32 day) external {
        if (!registered[indexId]) revert NotRegistered();
        Observation storage o = _obs[indexId][day];
        if (o.voided) revert DayVoided();
        if (o.posted) revert AlreadyPosted();
        IndexConfig memory c = _cfg[indexId];
        if (block.timestamp < _fetchAt(c, day) + c.disputeWindow + c.voidGrace) revert TooEarly();
        o.voided = true;
        emit Voided(indexId, day);
    }

    // ---- views ----

    function getFinal(bytes32 indexId, uint32 day) external view returns (int64) {
        Observation storage o = _obs[indexId][day];
        if (!o.finalized) revert NotFinal();
        return o.value;
    }

    function isActive(bytes32 indexId) external view returns (bool) {
        return registered[indexId] && _cfg[indexId].active;
    }

    function isVoid(bytes32 indexId, uint32 day) external view returns (bool) {
        return _obs[indexId][day].voided;
    }

    function observation(bytes32 indexId, uint32 day) external view returns (Observation memory) {
        return _obs[indexId][day];
    }

    function indexConfig(bytes32 indexId) external view returns (IndexConfig memory) {
        return _cfg[indexId];
    }

    function fetchAt(bytes32 indexId, uint32 day) external view returns (uint64) {
        return uint64(_fetchAt(_cfg[indexId], day));
    }

    function finalizeAt(bytes32 indexId, uint32 day) external view returns (uint64) {
        IndexConfig memory c = _cfg[indexId];
        return uint64(_fetchAt(c, day) + c.disputeWindow);
    }

    function reportDigest(bytes32 indexId, uint32 day, int64 value, uint16 revision, uint64 asOf)
        external
        view
        returns (bytes32)
    {
        return _digest(indexId, day, value, revision, asOf);
    }

    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }

    function _fetchAt(IndexConfig memory c, uint32 day) internal pure returns (uint256) {
        return (uint256(day) + 1) * DAY + c.fetchLag;
    }

    function _digest(bytes32 indexId, uint32 day, int64 value, uint16 revision, uint64 asOf)
        internal
        view
        returns (bytes32)
    {
        return _hashTypedDataV4(keccak256(abi.encode(REPORT_TYPEHASH, indexId, day, value, revision, asOf)));
    }
}
